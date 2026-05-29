"""
Options Flow Scanner — detects unusual activity using Polygon options chain snapshots
as the primary data source, falling back to yfinance if Polygon returns nothing.

For each ticker in the universe:
  1. Fetch price via Polygon snapshot (fallback: Finnhub quote)
  2. Fetch full options chain snapshot from Polygon (Greeks, IV, volume, OI included)
  3. For each contract, compute vol/OI anomalies and notional premium
  4. Flag contracts where vol/OI ≥ 2x with meaningful volume
  5. If Polygon returns empty, fall back to yfinance options chain scan
  6. Pass top alerts to Claude for interpretation
"""
import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

logger = logging.getLogger(__name__)

# Most liquid US equity options — highest volume, tightest spreads
FLOW_UNIVERSE = [
    # ETFs first — highest options volume, most reliable data
    "SPY", "QQQ", "IWM", "SOXL", "TQQQ", "GLD",
    # Mega-cap tech
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA",
    # Semiconductors
    "AMD", "AVGO", "MU",
    # High-IV momentum
    "PLTR", "COIN", "MSTR", "HOOD",
    # Financials
    "JPM", "GS", "BAC",
    # Other liquid names
    "NFLX", "UBER", "CRWD", "NOW",
    # Biotech
    "LLY", "MRNA",
]

MIN_VOLUME = 200
MIN_VOL_OI_RATIO = 2.0
MIN_NOTIONAL = 10_000
MAX_ALERTS_PER_TICKER = 2


def _earnings_context(ticker: str) -> str | None:
    try:
        from services.finnhub_client import get_earnings_this_month
        days = get_earnings_this_month(ticker)
        if days is None:
            return None
        if days == 0:
            return "Earnings today"
        if 1 <= days <= 30:
            return f"Earnings in {days}d"
        return None
    except Exception:
        return None


def _get_price_polygon(ticker: str) -> float | None:
    """Fetch current price from Polygon snapshot. Returns None on failure."""
    try:
        from services.polygon_client import _client
        snap = _client().get_snapshot_ticker("stocks", ticker)
        if snap and snap.day and snap.day.close and float(snap.day.close) > 0:
            return float(snap.day.close)
        if snap and snap.last_trade and snap.last_trade.price and float(snap.last_trade.price) > 0:
            return float(snap.last_trade.price)
    except Exception as e:
        logger.debug("Polygon price snapshot failed for %s: %s", ticker, e)
    return None


def _get_price_finnhub(ticker: str) -> float | None:
    """Fetch current price from Finnhub quote. Returns None on failure."""
    try:
        from services.finnhub_client import get_quote
        q = get_quote(ticker)
        price = float(q.get("c") or 0)
        return price if price > 0 else None
    except Exception as e:
        logger.debug("Finnhub price failed for %s: %s", ticker, e)
    return None


def _fetch_ticker_flow_polygon(ticker: str, price: float, earnings_ctx: str | None) -> list[dict]:
    """Scan a ticker using Polygon options chain snapshots. Returns alert dicts."""
    from services.polygon_client import get_options_chain_snapshot
    today = date.today()
    alerts = []

    # Fetch both calls and puts in one pass (no contract_type filter so we get both)
    snaps = get_options_chain_snapshot(
        ticker, dte_max=30, near_price=price, strike_pct_range=0.25
    )
    if not snaps:
        return []

    for snap in snaps:
        try:
            details = snap.details
            if not details:
                continue

            strike = float(details.strike_price or 0)
            if strike <= 0:
                continue

            opt_type = (details.contract_type or "").lower()
            if opt_type not in ("call", "put"):
                continue

            expiry_str = details.expiration_date  # "YYYY-MM-DD"
            if not expiry_str:
                continue
            expiry_dt = date.fromisoformat(expiry_str)
            dte = (expiry_dt - today).days
            if dte < 0:
                continue

            volume = int(snap.day.volume or 0) if snap.day else 0
            if volume < MIN_VOLUME:
                continue

            oi = int(snap.open_interest or 0)
            vol_oi_ratio = round(volume / oi, 1) if oi > 0 else 99.0
            is_new_contract = oi == 0

            if vol_oi_ratio < MIN_VOL_OI_RATIO and oi >= 500:
                continue

            # Mid premium: prefer last_quote midpoint, then (bid+ask)/2, then last_trade
            mid = 0.0
            bid = 0.0
            ask = 0.0
            if snap.last_quote:
                bid = float(snap.last_quote.bid or 0)
                ask = float(snap.last_quote.ask or 0)
                if snap.last_quote.midpoint and float(snap.last_quote.midpoint) > 0:
                    mid = float(snap.last_quote.midpoint)
                elif bid > 0 and ask > 0:
                    mid = round((bid + ask) / 2, 2)
            if mid <= 0 and snap.last_trade and snap.last_trade.price:
                mid = float(snap.last_trade.price or 0)
            if mid <= 0:
                continue

            notional = round(volume * mid * 100)
            if notional < MIN_NOTIONAL:
                continue

            iv_pct = None
            if snap.implied_volatility:
                iv_pct = round(float(snap.implied_volatility) * 100, 1)

            if opt_type == "call":
                pct_otm = round((strike - price) / price * 100, 1)
                breakeven = round(strike + mid, 2)
                pct_move_needed = round((breakeven - price) / price * 100, 1)
            else:
                pct_otm = round((price - strike) / price * 100, 1)
                breakeven = round(strike - mid, 2)
                pct_move_needed = round((price - breakeven) / price * 100, 1)

            # Greeks — may be None when market is closed
            delta = gamma = theta = vega = None
            if snap.greeks:
                delta = round(float(snap.greeks.delta), 2) if snap.greeks.delta is not None else None
                gamma = round(float(snap.greeks.gamma), 4) if snap.greeks.gamma is not None else None
                theta = round(float(snap.greeks.theta), 2) if snap.greeks.theta is not None else None
                vega = round(float(snap.greeks.vega), 2) if snap.greeks.vega is not None else None

            alerts.append({
                "ticker": ticker,
                "price": round(price, 2),
                "option_type": opt_type,
                "strike": strike,
                "expiry": expiry_str,
                "dte": dte,
                "volume": volume,
                "open_interest": oi,
                "vol_oi_ratio": vol_oi_ratio,
                "is_new_contract": is_new_contract,
                "mid_premium": round(mid, 2),
                "bid": round(bid, 2),
                "ask": round(ask, 2),
                "notional": notional,
                "pct_otm": pct_otm,
                "sentiment": "bullish" if opt_type == "call" else "bearish",
                "earnings_context": earnings_ctx,
                "breakeven": breakeven,
                "pct_move_needed": pct_move_needed,
                "iv_pct": iv_pct,
                "hv_pct": None,
                "iv_hv_ratio": None,
                "premium_rating": None,
                "delta": delta,
                "gamma": gamma,
                "theta": theta,
                "vega": vega,
            })
        except Exception:
            continue

    return alerts


def _fetch_ticker_flow_yfinance(ticker: str, earnings_ctx: str | None) -> list[dict]:
    """Fallback: scan a ticker using yfinance options chains. Returns alert dicts."""
    import yfinance as yf
    import pandas as pd

    t = yf.Ticker(ticker)

    price = None
    try:
        price = float(t.fast_info.last_price or 0)
    except Exception:
        pass
    if not price or price <= 0:
        return []

    expiries = t.options
    if not expiries:
        return []
    expiries_to_scan = expiries[:2]

    today = date.today()
    alerts = []

    for expiry_str in expiries_to_scan:
        try:
            chain = t.option_chain(expiry_str)
        except Exception:
            continue

        expiry_dt = date.fromisoformat(expiry_str)
        dte = (expiry_dt - today).days

        for opt_type, df in [("call", chain.calls), ("put", chain.puts)]:
            if df is None or df.empty:
                continue
            for _, row in df.iterrows():
                try:
                    strike = float(row.get("strike") or 0)
                    if strike <= 0:
                        continue

                    volume = int(row.get("volume") or 0)
                    if volume < MIN_VOLUME:
                        continue

                    oi = int(row.get("openInterest") or 0)
                    vol_oi_ratio = round(volume / oi, 1) if oi > 0 else 99.0
                    is_new_contract = oi == 0

                    if vol_oi_ratio < MIN_VOL_OI_RATIO and oi >= 500:
                        continue

                    bid = float(row.get("bid") or 0)
                    ask = float(row.get("ask") or 0)
                    mid = round((bid + ask) / 2, 2) if bid > 0 else float(row.get("lastPrice") or 0)
                    if mid <= 0:
                        continue

                    notional = round(volume * mid * 100)
                    if notional < MIN_NOTIONAL:
                        continue

                    iv_pct = round(float(row.get("impliedVolatility") or 0) * 100, 1) or None

                    if opt_type == "call":
                        pct_otm = round((strike - price) / price * 100, 1)
                        breakeven = round(strike + mid, 2)
                        pct_move_needed = round((breakeven - price) / price * 100, 1)
                    else:
                        pct_otm = round((price - strike) / price * 100, 1)
                        breakeven = round(strike - mid, 2)
                        pct_move_needed = round((price - breakeven) / price * 100, 1)

                    alerts.append({
                        "ticker": ticker,
                        "price": round(price, 2),
                        "option_type": opt_type,
                        "strike": strike,
                        "expiry": expiry_str,
                        "dte": dte,
                        "volume": volume,
                        "open_interest": oi,
                        "vol_oi_ratio": vol_oi_ratio,
                        "is_new_contract": is_new_contract,
                        "mid_premium": mid,
                        "bid": bid,
                        "ask": ask,
                        "notional": notional,
                        "pct_otm": pct_otm,
                        "sentiment": "bullish" if opt_type == "call" else "bearish",
                        "earnings_context": earnings_ctx,
                        "breakeven": breakeven,
                        "pct_move_needed": pct_move_needed,
                        "iv_pct": iv_pct,
                        "hv_pct": None,
                        "iv_hv_ratio": None,
                        "premium_rating": None,
                        "delta": None,
                        "gamma": None,
                        "theta": None,
                        "vega": None,
                    })
                except Exception:
                    continue

    return alerts


def _fetch_ticker_flow(ticker: str) -> list[dict]:
    """Return unusual flow alerts for a single ticker.

    Primary path: Polygon options chain snapshot (includes Greeks).
    Fallback: yfinance options chain scan if Polygon returns nothing.
    """
    try:
        earnings_ctx = _earnings_context(ticker)

        # --- Price: Polygon first, Finnhub fallback ---
        price = _get_price_polygon(ticker)
        if not price:
            price = _get_price_finnhub(ticker)
        if not price or price <= 0:
            return []

        # --- Primary: Polygon options chain snapshot ---
        alerts: list[dict] = []
        try:
            alerts = _fetch_ticker_flow_polygon(ticker, price, earnings_ctx)
        except Exception as e:
            logger.warning("Polygon options scan failed for %s: %s", ticker, e)

        # --- Fallback: yfinance if Polygon returned nothing ---
        if not alerts:
            logger.debug("Polygon returned no alerts for %s, falling back to yfinance", ticker)
            try:
                alerts = _fetch_ticker_flow_yfinance(ticker, earnings_ctx)
            except Exception as e:
                logger.warning("yfinance fallback also failed for %s: %s", ticker, e)

        alerts.sort(key=lambda x: x["notional"], reverse=True)
        top = alerts[:MAX_ALERTS_PER_TICKER]
        logger.info("flow scan %s: %d alerts (polygon primary)", ticker, len(top))
        return top

    except Exception as e:
        logger.warning("flow scan failed for %s: %s", ticker, e)
        return []


def run_flow_scan() -> dict:
    """Scan the options universe and return AI-interpreted unusual flow alerts."""
    from services.claude_analyst import ClaudeAnalyst

    all_alerts: list[dict] = []

    universe = FLOW_UNIVERSE[:]
    random.shuffle(universe)

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_fetch_ticker_flow, t): t for t in universe}
        try:
            for fut in as_completed(futures, timeout=90):
                try:
                    all_alerts.extend(fut.result(timeout=20))
                except Exception:
                    pass
        except Exception:
            # Timeout — use whatever results came in before the deadline
            for fut in futures:
                if fut.done():
                    try:
                        all_alerts.extend(fut.result())
                    except Exception:
                        pass

    if not all_alerts:
        return {
            "alerts": [],
            "tickers_scanned": len(FLOW_UNIVERSE),
            "total_alerts_found": 0,
            "error": "No unusual options flow detected. Market may be closed or activity is within normal ranges.",
        }

    all_alerts.sort(key=lambda x: x["notional"], reverse=True)
    seen: set = set()
    deduped = []
    for a in all_alerts:
        key = (a["ticker"], a["option_type"], a["strike"], a["expiry"])
        if key not in seen:
            seen.add(key)
            deduped.append(a)
    top = deduped[:20]

    # Enrich top alerts with catalyst data: today's % move + recent news
    seen_tickers: dict = {}
    for alert in top:
        ticker = alert["ticker"]
        if ticker not in seen_tickers:
            catalyst: dict = {"change_pct": None, "news": []}
            try:
                from services.finnhub_client import get_quote
                q = get_quote(ticker)
                prev = float(q.get("pc") or 0)
                curr = float(q.get("c") or 0)
                if prev > 0:
                    catalyst["change_pct"] = round((curr - prev) / prev * 100, 2)
            except Exception:
                pass
            try:
                from services.polygon_client import get_news
                raw = get_news(ticker, limit=3)
                catalyst["news"] = [n.get("title", "") for n in raw if n.get("title")]
            except Exception:
                pass
            seen_tickers[ticker] = catalyst
        alert["change_pct"] = seen_tickers[ticker]["change_pct"]
        alert["news"] = seen_tickers[ticker]["news"]

    call_notional = sum(a["notional"] for a in all_alerts if a["option_type"] == "call")
    put_notional = sum(a["notional"] for a in all_alerts if a["option_type"] == "put")
    total_notional = call_notional + put_notional
    sentiment_ratio = round(call_notional / total_notional * 100) if total_notional > 0 else 50
    overall = "bullish" if sentiment_ratio > 55 else ("bearish" if sentiment_ratio < 45 else "neutral")

    analyst = ClaudeAnalyst()
    interpreted = analyst.interpret_options_flow(top, sentiment_ratio, overall)

    return {
        "alerts": interpreted,
        "tickers_scanned": len(FLOW_UNIVERSE),
        "total_alerts_found": len(all_alerts),
        "call_notional": call_notional,
        "put_notional": put_notional,
        "sentiment_ratio": sentiment_ratio,
        "overall_sentiment": overall,
        "data_source": "polygon_options + finnhub",
    }
