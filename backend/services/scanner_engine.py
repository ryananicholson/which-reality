"""
Day Trade Scanner — Polygon-based universe scan with technical indicators.

Flow:
1. Fetch market status from Polygon
2. Batch snapshots for the curated 150-stock universe + SPY via Polygon
3. First-pass filter for price, volume, and % change thresholds
4. Fetch OHLCV bars for top candidates; compute RSI-14, ATR-14, MA-20
5. Enrich top candidates with news headlines from Polygon
6. Pass enriched candidates to Claude for high-confidence play selection
"""
import logging
import math
from datetime import date

import pandas as pd

logger = logging.getLogger(__name__)

MIN_PRICE = 5.0
MAX_PRICE = 600.0
MIN_VOLUME = 200_000
MIN_CHANGE_PCT = 1.5

SCAN_UNIVERSE = [
    # Mega-cap tech
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "AVGO", "ORCL",
    # Semiconductors
    "AMD", "INTC", "QCOM", "TXN", "MU", "SMCI", "ARM",
    # Financials
    "JPM", "BAC", "GS", "MS", "V", "MA", "PYPL", "SQ",
    # High-IV momentum / retail favorites
    "PLTR", "COIN", "HOOD", "SOFI", "RIVN", "SHOP", "SNAP", "UBER", "LYFT",
    "MSTR", "RBLX", "DUOL", "DKNG", "PENN",
    # Biotech / pharma
    "LLY", "ABBV", "PFE", "MRNA", "BNTX", "REGN", "BIIB", "GILD",
    # Energy
    "XOM", "CVX", "OXY", "SLB", "HAL",
    # Consumer / retail
    "COST", "HD", "WMT", "NKE", "MCD", "SBUX", "CMG",
    # Media / streaming
    "NFLX", "DIS", "SPOT", "ROKU",
    # Software / cloud
    "CRM", "NOW", "ADBE", "SNOW", "DDOG", "ZM", "OKTA", "CRWD", "S",
    # EV / clean energy
    "RIVN", "LCID", "NIO", "XPEV", "LI", "PLUG", "FSLR",
    # Other high-volume
    "F", "GM", "BA", "GE", "T", "VZ", "C", "WFC",
    # ETFs with options + high volume
    "SPY", "QQQ", "IWM", "ARKK", "XLE", "GLD", "SLV", "SOXL", "TQQQ", "SQQQ",
]
# Deduplicate while preserving order
_seen = set()
SCAN_UNIVERSE = [t for t in SCAN_UNIVERSE if not (t in _seen or _seen.add(t))]


def _rsi(prices: pd.Series, period: int = 14) -> float | None:
    delta = prices.diff()
    gain = delta.where(delta > 0, 0.0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    val = rsi.iloc[-1]
    return round(float(val), 1) if pd.notna(val) else None


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float | None:
    prev = close.shift(1)
    tr = pd.concat([high - low, (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    val = atr.iloc[-1]
    return round(float(val), 2) if pd.notna(val) else None


def _ma(prices: pd.Series, period: int) -> float | None:
    if len(prices) < period:
        return None
    val = prices.rolling(period).mean().iloc[-1]
    return round(float(val), 2) if pd.notna(val) else None


def _fetch_movers_yfinance() -> tuple[list[dict], float | None]:
    """Fallback: download 30d of OHLCV for the universe + SPY via yfinance, compute technicals, return movers + SPY change."""
    import yfinance as yf
    tickers_to_fetch = list(dict.fromkeys(["SPY"] + SCAN_UNIVERSE))
    try:
        raw = yf.download(
            tickers_to_fetch,
            period="30d",
            interval="1d",
            progress=False,
            threads=True,
            auto_adjust=True,
        )
    except Exception as e:
        logger.error("yfinance batch download failed: %s", e)
        return [], None

    # Compute SPY's today-vs-yesterday change for relative strength
    spy_change = None
    try:
        spy_close = raw["Close"]["SPY"].dropna()
        if len(spy_close) >= 2:
            spy_change = round((float(spy_close.iloc[-1]) - float(spy_close.iloc[-2])) / float(spy_close.iloc[-2]) * 100, 2)
    except Exception:
        pass

    candidates = []
    for ticker in SCAN_UNIVERSE:
        try:
            close = raw["Close"][ticker].dropna()
            volume = raw["Volume"][ticker].dropna()
            high = raw["High"][ticker].dropna()
            low = raw["Low"][ticker].dropna()
            open_ = raw["Open"][ticker].dropna()

            if len(close) < 2 or len(volume) < 2:
                continue

            price = float(close.iloc[-1])
            prev_close = float(close.iloc[-2])
            vol_today = float(volume.iloc[-1])
            vol_prev = float(volume.iloc[-2]) if len(volume) >= 2 else vol_today

            if price < MIN_PRICE or price > MAX_PRICE:
                continue
            if vol_today < MIN_VOLUME:
                continue

            change_pct = (price - prev_close) / prev_close * 100
            if abs(change_pct) < MIN_CHANGE_PCT:
                continue

            vol_ratio = round(vol_today / vol_prev, 1) if vol_prev > 0 else 1.0
            day_high = float(high.iloc[-1])
            day_low = float(low.iloc[-1])
            day_open = float(open_.iloc[-1])
            vwap = round((day_high + day_low + price) / 3, 2)

            rsi = _rsi(close)
            atr = _atr(high, low, close)
            ma20 = _ma(close, 20)
            vs_spy = round(change_pct - spy_change, 2) if spy_change is not None else None

            # 52-week context: how far from 52-week high/low?
            hi52 = round(float(high.max()), 2) if len(high) >= 50 else None
            lo52 = round(float(low.min()), 2) if len(low) >= 50 else None

            candidates.append({
                "ticker": ticker,
                "price": round(price, 2),
                "change_pct": round(change_pct, 2),
                "volume_m": round(vol_today / 1_000_000, 1),
                "vol_ratio": vol_ratio,
                "high": round(day_high, 2),
                "low": round(day_low, 2),
                "open": round(day_open, 2),
                "vwap": vwap,
                "prev_close": round(prev_close, 2),
                "direction": "up" if change_pct > 0 else "down",
                "rsi": rsi,
                "atr": atr,
                "ma20": ma20,
                "vs_spy": vs_spy,
                "hi52": hi52,
                "lo52": lo52,
                "days_to_cover": None,
                "short_volume_ratio_pct": None,
            })
        except Exception as e:
            logger.debug("skipping %s: %s", ticker, e)

    return candidates, spy_change


def _fetch_movers() -> tuple[list[dict], float | None]:
    """Batch-snapshot the universe via Polygon, enrich top candidates with OHLCV bars, return movers + SPY change."""
    from services.polygon_client import get_snapshots_batch, get_ohlcv_bars, get_news

    tickers_to_fetch = list(dict.fromkeys(["SPY"] + SCAN_UNIVERSE))
    snapshots = get_snapshots_batch(tickers_to_fetch)

    if not snapshots:
        # Fallback to yfinance if Polygon batch fails
        return _fetch_movers_yfinance()

    # SPY change for relative strength
    spy_change = snapshots.get("SPY", {}).get("change_pct")

    # First-pass filter: price, volume, change threshold
    candidates = []
    for ticker in SCAN_UNIVERSE:
        snap = snapshots.get(ticker)
        if not snap:
            continue
        price = snap["price"]
        volume = snap["volume"]
        change_pct = snap["change_pct"]

        if price < MIN_PRICE or price > MAX_PRICE:
            continue
        if volume < MIN_VOLUME:
            continue
        if abs(change_pct) < MIN_CHANGE_PCT:
            continue

        prev_close = snap["prev_close"] or price / (1 + change_pct / 100)
        vol_ratio = 1.0  # will compute from bars below

        candidates.append({
            "ticker": ticker,
            "price": round(price, 2),
            "change_pct": round(change_pct, 2),
            "volume_m": round(volume / 1_000_000, 1),
            "vol_ratio": vol_ratio,
            "high": round(snap["high"], 2),
            "low": round(snap["low"], 2),
            "open": round(snap["open"], 2),
            "vwap": round(snap["vwap"], 2) if snap["vwap"] else round((snap["high"] + snap["low"] + price) / 3, 2),
            "prev_close": round(prev_close, 2),
            "direction": "up" if change_pct > 0 else "down",
            "rsi": None,
            "atr": None,
            "ma20": None,
            "vs_spy": round(change_pct - spy_change, 2) if spy_change is not None else None,
            "hi52": None,
            "lo52": None,
            "days_to_cover": None,
            "short_volume_ratio_pct": None,
        })

    # Second pass: enrich top candidates with RSI/ATR/MA from Polygon OHLCV bars
    # Sort by abs change first to get the most important ones
    candidates.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
    top_candidates = candidates[:20]  # only fetch bars for top 20

    for cand in top_candidates:
        try:
            bars = get_ohlcv_bars(cand["ticker"], days=35)
            if len(bars) < 5:
                continue

            closes = pd.Series([b["c"] for b in bars])
            highs = pd.Series([b["h"] for b in bars])
            lows = pd.Series([b["l"] for b in bars])
            volumes = pd.Series([b["v"] for b in bars])

            cand["rsi"] = _rsi(closes)
            cand["atr"] = _atr(highs, lows, closes)
            cand["ma20"] = _ma(closes, 20)

            if len(volumes) >= 2:
                vol_today = volumes.iloc[-1]
                vol_prev = volumes.iloc[-2]
                if vol_prev > 0:
                    cand["vol_ratio"] = round(vol_today / vol_prev, 1)

            if len(closes) >= 50:
                cand["hi52"] = round(float(highs.max()), 2)
                cand["lo52"] = round(float(lows.min()), 2)
        except Exception:
            pass

    return top_candidates, spy_change


def _norm_cdf(x: float) -> float:
    return (1.0 + math.erf(x / math.sqrt(2))) / 2


def _bs_delta(S: float, K: float, T_years: float, sigma: float, option_type: str, r: float = 0.05) -> float | None:
    """Black-Scholes delta (≈ probability of expiring ITM)."""
    if T_years <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return None
    try:
        d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T_years) / (sigma * math.sqrt(T_years))
        return round(_norm_cdf(d1) if option_type == "CALL" else _norm_cdf(d1) - 1, 2)
    except Exception:
        return None


def _snap_option(ticker: str, option_type: str, suggested_strike: float, suggested_expiry: str) -> dict | None:
    """Fetch real-time quote + Greeks from Polygon for the closest available strike/expiry."""
    try:
        from services.polygon_client import get_options_chain_snapshot
        snapshots = get_options_chain_snapshot(
            ticker, dte_max=30, contract_type=option_type.lower(),
            near_price=suggested_strike, strike_pct_range=0.15,
        )
        if not snapshots:
            return None

        today = date.today()
        try:
            target_dt = date.fromisoformat(suggested_expiry)
        except Exception:
            target_dt = today

        # Score each contract by proximity to suggested strike + expiry
        best = None
        best_score = float("inf")
        for snap in snapshots:
            if not snap.details:
                continue
            strike = float(snap.details.strike_price or 0)
            if strike <= 0:
                continue
            try:
                exp_dt = date.fromisoformat(str(snap.details.expiration_date))
            except Exception:
                continue
            exp_diff = abs((exp_dt - target_dt).days)
            strike_diff = abs(strike - suggested_strike)
            score = exp_diff * 3 + strike_diff
            if score < best_score:
                best_score = score
                best = snap

        if not best or not best.details:
            return None

        strike = float(best.details.strike_price)
        expiry = str(best.details.expiration_date)
        dte = (date.fromisoformat(expiry) - today).days

        bid = ask = mid = 0.0
        if best.last_quote:
            bid = float(best.last_quote.bid or 0)
            ask = float(best.last_quote.ask or 0)
            mp = best.last_quote.midpoint
            mid = float(mp) if mp else (round((bid + ask) / 2, 2) if bid > 0 else 0.0)
        if mid <= 0 and best.last_trade:
            mid = float(best.last_trade.price or 0)
        if mid <= 0:
            return None

        price = None
        if best.underlying_asset and best.underlying_asset.price:
            price = float(best.underlying_asset.price)
        if not price or price <= 0:
            return None

        if option_type.upper() == "CALL":
            breakeven = round(strike + mid, 2)
        else:
            breakeven = round(strike - mid, 2)
        pct_move = round(abs(breakeven - price) / price * 100, 1)

        # Real Greeks — no BS approximation needed
        delta = gamma = theta = vega = None
        if best.greeks:
            delta = round(float(best.greeks.delta), 2) if best.greeks.delta is not None else None
            gamma = round(float(best.greeks.gamma), 4) if best.greeks.gamma is not None else None
            theta = round(float(best.greeks.theta), 2) if best.greeks.theta is not None else None
            vega = round(float(best.greeks.vega), 2) if best.greeks.vega is not None else None

        iv_pct = round(float(best.implied_volatility) * 100, 1) if best.implied_volatility else None

        # Fall back to BS delta only if Polygon didn't return Greeks (e.g. market closed)
        if delta is None and iv_pct:
            T_years = max(dte, 1) / 365
            delta = _bs_delta(price, strike, T_years, best.implied_volatility, option_type.upper())

        return {
            "option_type": option_type.upper(),
            "strike": strike,
            "expiry": expiry,
            "dte": dte,
            "entry_premium": round(mid, 2),
            "bid": round(bid, 2),
            "ask": round(ask, 2),
            "breakeven_stock": breakeven,
            "pct_move_needed": pct_move,
            "delta": delta,
            "gamma": gamma,
            "theta": theta,
            "vega": vega,
            "iv_pct": iv_pct,
        }
    except Exception as e:
        logger.debug("snap_option failed for %s: %s", ticker, e)
        return None


def run_scan() -> dict:
    """Run the day trade scan and return Claude's top plays."""
    from services.claude_analyst import ClaudeAnalyst

    market_status = None
    try:
        from services.polygon_client import get_market_status
        market_status = get_market_status()
    except Exception as e:
        logger.warning("market_status fetch failed: %s", e)

    candidates, spy_change = _fetch_movers()

    if not candidates:
        return {
            "plays": [],
            "candidates_scanned": 0,
            "market_status": market_status,
            "spy_change": spy_change,
            "error": "No qualifying movers found. Market may be closed or all moves are below threshold.",
        }

    # Sort by vol_ratio first (conviction), then by abs change
    candidates.sort(key=lambda x: (x["vol_ratio"], abs(x["change_pct"])), reverse=True)
    top = candidates[:15]

    # Enrich with news headlines from Massive (graceful — free tier)
    for c in top:
        try:
            from services.polygon_client import get_news
            news = get_news(c["ticker"], limit=3)
            c["news"] = [n.get("title", "") for n in news if n.get("title")]
        except Exception:
            c["news"] = []

    analyst = ClaudeAnalyst()
    plays = analyst.scan_day_trades(top, spy_change=spy_change)

    # Snap each option suggestion to real chain data
    for play in plays:
        op = play.get("option_play")
        if not op or not op.get("option_type") or not op.get("strike"):
            continue
        try:
            snapped = _snap_option(
                play.get("ticker", ""),
                op["option_type"],
                float(op["strike"]),
                op.get("expiry", ""),
            )
        except Exception as e:
            logger.debug("snap_option error for %s: %s", play.get("ticker"), e)
            snapped = None

        if snapped:
            # Preserve Claude's target/stop estimates; replace entry with real market data
            snapped["target_premium"] = op.get("target_premium")
            snapped["stop_premium"] = op.get("stop_premium")

            # Move feasibility: pct move needed ÷ ATR% (how many typical daily ranges)
            mover = next((m for m in top if m["ticker"] == play.get("ticker")), None)
            if mover and mover.get("atr") and mover.get("price") and snapped.get("pct_move_needed"):
                atr_pct = mover["atr"] / mover["price"] * 100
                if atr_pct > 0:
                    feasibility = round(snapped["pct_move_needed"] / atr_pct, 1)
                    snapped["move_feasibility"] = feasibility

            # Combined likelihood label from delta + feasibility
            delta = snapped.get("delta")
            feas = snapped.get("move_feasibility")
            abs_delta = abs(delta) if delta is not None else None

            if abs_delta is not None and feas is not None:
                if abs_delta >= 0.45 and feas <= 1.0:
                    label = "likely"
                elif abs_delta >= 0.30 and feas <= 1.8:
                    label = "possible"
                else:
                    label = "speculative"
            elif abs_delta is not None:
                label = "likely" if abs_delta >= 0.45 else ("possible" if abs_delta >= 0.30 else "speculative")
            elif feas is not None:
                label = "likely" if feas <= 1.0 else ("possible" if feas <= 1.8 else "speculative")
            else:
                label = None
            snapped["likelihood"] = label
            play["option_play"] = snapped
        else:
            # Snap failed — compute likelihood from Claude's estimates + mover ATR/price
            mover = next((m for m in top if m["ticker"] == play.get("ticker")), None)
            strike = float(op.get("strike") or 0)
            expiry_str = op.get("expiry", "")
            opt_type = (op.get("option_type") or "CALL").upper()

            dte = 7
            try:
                dte = max(1, (date.fromisoformat(expiry_str) - date.today()).days)
            except Exception:
                pass
            op["dte"] = dte

            delta = None
            feas = None
            if mover and mover.get("atr") and mover.get("price") and strike > 0:
                price = mover["price"]
                atr_daily = mover["atr"] / price
                # Rough annualised vol from ATR (ATR ≈ 1.25× daily std for many stocks)
                iv_est = atr_daily * (252 ** 0.5) * 0.8
                delta = _bs_delta(price, strike, dte / 365, iv_est, opt_type)

                entry = float(op.get("entry_premium") or 0)
                if entry > 0:
                    if opt_type == "CALL":
                        breakeven = round(strike + entry, 2)
                        pct_move = round((breakeven - price) / price * 100, 1)
                    else:
                        breakeven = round(strike - entry, 2)
                        pct_move = round((price - breakeven) / price * 100, 1)
                    op.setdefault("breakeven_stock", breakeven)
                    op.setdefault("pct_move_needed", pct_move)
                    atr_pct = atr_daily * 100
                    if atr_pct > 0:
                        feas = round(pct_move / atr_pct, 1)
                        op["move_feasibility"] = feas

                op["delta"] = delta

            abs_delta = abs(delta) if delta is not None else None
            if abs_delta is not None and feas is not None:
                if abs_delta >= 0.45 and feas <= 1.0:
                    label = "likely"
                elif abs_delta >= 0.30 and feas <= 1.8:
                    label = "possible"
                else:
                    label = "speculative"
            elif abs_delta is not None:
                label = "likely" if abs_delta >= 0.45 else ("possible" if abs_delta >= 0.30 else "speculative")
            elif feas is not None:
                label = "likely" if feas <= 1.0 else ("possible" if feas <= 1.8 else "speculative")
            else:
                label = "speculative"
            op["likelihood"] = label
            play["option_play"] = op

    return {
        "plays": plays,
        "candidates_scanned": len(candidates),
        "top_movers": top,
        "market_status": market_status,
        "spy_change": spy_change,
        "data_note": f"Scanned {len(SCAN_UNIVERSE)}-stock universe · polygon_live · RSI + ATR enriched",
    }
