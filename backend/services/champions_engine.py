"""
Champions Engine — daily market-open scan.

1. Pre-screens ~50 curated stocks via Finnhub (reliable API, no IP blocking).
2. Passes survivors to Claude in ONE batched call.
3. Stores three champion records (wheel / options / longterm) in the DB.
"""
import logging
from datetime import datetime, timezone

import pandas as pd

logger = logging.getLogger(__name__)

UNIVERSE = [
    # Blue chips / Dow components
    "AAPL", "MSFT", "JPM", "JNJ", "KO", "HD", "V", "UNH", "MCD", "WMT",
    # High-IV momentum
    "NVDA", "AMD", "TSLA", "META", "AMZN", "GOOGL", "NFLX", "CRM", "SHOP", "PLTR",
    # Solid wheel candidates
    "COST", "PG", "ABT", "MMM", "T", "VZ", "PFE", "XOM", "CVX", "BAC",
    # Growth / income mix
    "ABBV", "LLY", "TMO", "AVGO", "NOW", "ADBE", "QCOM", "TXN", "BMY", "MO",
    # High-volume mid-caps
    "F", "GM", "UBER", "NKE", "SNAP", "SOFI", "COIN", "RIVN", "HOOD", "LYFT",
    # ETFs with liquid options and meaningful IV for wheel/covered-call strategies
    "QQQ", "SCHD", "GLD", "SLV", "IWM", "XLE", "EWZ",
]

MIN_PRICE = 3.0
MIN_AVG_VOLUME = 300_000
RSI_LOW, RSI_HIGH = 20.0, 80.0
EARNINGS_BUFFER_DAYS = 14


def _rsi(closes: list[float], period: int = 14) -> float | None:
    try:
        if len(closes) < period + 1:
            return None
        s = pd.Series(closes)
        delta = s.diff()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        rs = gain / loss.replace(0, float("nan"))
        val = (100 - (100 / (1 + rs))).iloc[-1]
        return round(float(val), 1) if pd.notna(val) else None
    except Exception:
        return None


def _get_closes_volumes(ticker: str) -> tuple[list, list]:
    """OHLCV history: Finnhub candles first, yfinance per-ticker fallback."""
    from services.finnhub_client import get_candles
    candles = get_candles(ticker, days=100)
    if candles.get("s") == "ok" and candles.get("c"):
        return candles["c"], candles.get("v", [])
    # Finnhub free tier doesn't include candles — fall back to yfinance per-ticker
    try:
        import yfinance as yf
        hist = yf.Ticker(ticker).history(period="6mo")
        if not hist.empty:
            return hist["Close"].tolist(), hist["Volume"].tolist()
    except Exception as e:
        logger.debug("Champions yfinance fallback failed for %s: %s", ticker, e)
    return [], []


def _screen_ticker(ticker: str) -> dict | None:
    """Fetch price history and apply basic filters. Returns dict or None."""
    from services.finnhub_client import get_earnings_this_month

    closes, volumes = _get_closes_volumes(ticker)
    if not closes or len(closes) < 20:
        return None

    price = float(closes[-1])
    avg_vol = float(sum(volumes[-20:]) / 20) if len(volumes) >= 20 else 0

    if price < MIN_PRICE or avg_vol < MIN_AVG_VOLUME:
        return None

    rsi = _rsi(closes)
    if rsi is not None and (rsi < RSI_LOW or rsi > RSI_HIGH):
        return None

    # Earnings check — skip if earnings within 14 days
    days_to_earnings = get_earnings_this_month(ticker)
    if days_to_earnings is not None and days_to_earnings <= EARNINGS_BUFFER_DAYS:
        logger.debug("Champions: skipping %s — earnings in %d days", ticker, days_to_earnings)
        return None

    high_60 = max(closes[-60:]) if len(closes) >= 60 else max(closes)
    low_60 = min(closes[-60:]) if len(closes) >= 60 else min(closes)

    return {
        "ticker": ticker,
        "price": round(price, 2),
        "avg_vol_m": round(avg_vol / 1_000_000, 1),
        "rsi": rsi,
        "pct_from_high": round((price - high_60) / high_60 * 100, 1),
        "pct_from_low": round((price - low_60) / low_60 * 100, 1),
    }


def prescreen() -> tuple[list[dict], str | None]:
    """
    Screens each ticker: Finnhub candles (paid) or yfinance per-ticker (free fallback).
    Returns (survivors, error_message).
    """
    from config import settings
    if not settings.finnhub_api_key:
        return [], "FINNHUB_API_KEY is not set — add it to your Render environment variables"

    logger.info("Champions: screening %d tickers via Finnhub", len(UNIVERSE))
    survivors = []
    errors = 0

    for ticker in UNIVERSE:
        try:
            result = _screen_ticker(ticker)
            if result:
                survivors.append(result)
        except Exception as e:
            errors += 1
            logger.debug("Champions: error screening %s: %s", ticker, e)

    logger.info(
        "Champions: %d/%d passed pre-screen (%d errors)",
        len(survivors), len(UNIVERSE), errors,
    )

    if not survivors:
        return [], (
            "No stocks passed the quality filter. "
            "This may be a Finnhub API issue — check that FINNHUB_API_KEY is set correctly."
        )

    return survivors, None


def run(db) -> tuple[bool, str | None]:
    """Returns (success, error_message)."""
    from models.champion import Champion
    from services.claude_analyst import ClaudeAnalyst

    survivors, err = prescreen()
    if err:
        return False, err

    if len(survivors) < 3:
        return False, f"Only {len(survivors)} stocks passed screening — need at least 3."

    analyst = ClaudeAnalyst()
    try:
        champions = analyst.pick_champions(survivors)
    except Exception as e:
        return False, f"AI analysis failed: {e}"

    if not champions or len(champions) < 2:
        return False, "AI returned incomplete results — try again."

    run_at = datetime.now(timezone.utc)
    db.query(Champion).delete()
    for strategy, data in champions.items():
        if not data or not data.get("ticker"):
            continue
        db.add(Champion(
            strategy=strategy,
            ticker=data["ticker"],
            score=data.get("score"),
            grade=data.get("grade"),
            reason=data.get("reason"),
            universe_size=len(UNIVERSE),
            survivors_count=len(survivors),
            run_at=run_at,
        ))
    db.commit()
    logger.info("Champions saved: %s", {s: d.get("ticker") for s, d in champions.items()})
    return True, None
