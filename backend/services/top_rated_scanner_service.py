"""
Top Rated Market Scanner — finds S&P 500 + Nasdaq 100 stocks scoring 6/8+ on the trigger system.

Architecture:
  Stage 1a: Polygon batch snapshot → price >= $15 + volume >= 1M filter
  Stage 1b: Sequential Finnhub fundamentals (24h disk cache) → mc/rev/margin/P-E filter
  Stage 2:  Full trigger scoring (MA, earnings, DCF, MC) on ~80 survivors
  Skip-MC:  If non_MC_earned + 2 < 6 (non_MC < 4), skip Monte Carlo entirely

Cache:
  /tmp/cache/fundamentals/{TICKER}.json  — Finnhub basic_financials, 24h TTL
  /tmp/cache/earnings/{TICKER}.json      — earnings calendar, 7-day TTL
  /tmp/scan_top_rated_result.json        — full scan result, 24h TTL
"""
import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

_REPO_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
_SP500_FILE = os.path.join(_REPO_DATA_DIR, "sp500.json")
_NDX100_FILE = os.path.join(_REPO_DATA_DIR, "nasdaq100.json")

_CACHE_DIR = "/tmp/tr_cache"
_FUND_CACHE_DIR = os.path.join(_CACHE_DIR, "fundamentals")
_EARN_CACHE_DIR = os.path.join(_CACHE_DIR, "earnings")
_RESULT_CACHE = "/tmp/scan_top_rated_result.json"

_FUND_TTL = 86_400       # 24 h
_EARN_TTL = 604_800      # 7 days
_RESULT_TTL = 86_400     # 24 h

_FINNHUB_INTERVAL = 1.2  # ~50 calls/min — safe for free tier

_progress: dict = {}
_progress_lock = threading.Lock()
_scan_lock = threading.Lock()


# ── Cache helpers ─────────────────────────────────────────────────────────────

def _ensure_dirs() -> None:
    os.makedirs(_FUND_CACHE_DIR, exist_ok=True)
    os.makedirs(_EARN_CACHE_DIR, exist_ok=True)


def _cache_read(path: str, ttl: int) -> dict | None:
    try:
        if not os.path.exists(path):
            return None
        if time.time() - os.path.getmtime(path) > ttl:
            return None
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def _cache_write(path: str, data: dict) -> None:
    try:
        with open(path, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logger.debug("Cache write failed %s: %s", path, e)


# ── Progress ──────────────────────────────────────────────────────────────────

def _set_progress(**kwargs) -> None:
    with _progress_lock:
        _progress.update(kwargs)


def get_scan_status() -> dict:
    with _progress_lock:
        return dict(_progress)


# ── Universe ──────────────────────────────────────────────────────────────────

def _load_universe() -> list[str]:
    tickers: set[str] = set()
    for path in (_SP500_FILE, _NDX100_FILE):
        try:
            with open(path) as f:
                tickers.update(json.load(f))
        except Exception as e:
            logger.warning("Failed to load universe file %s: %s", path, e)
    if not tickers:
        logger.error("Universe is empty — both sp500.json and nasdaq100.json missing?")
    return sorted(tickers)



# ── Stage 1b: Finnhub fundamentals ───────────────────────────────────────────

def _get_fundamentals(ticker: str) -> dict | None:
    path = os.path.join(_FUND_CACHE_DIR, f"{ticker}.json")
    cached = _cache_read(path, _FUND_TTL)
    if cached is not None:
        return cached

    from services.finnhub_client import get_basic_financials
    for attempt in range(3):
        metrics = get_basic_financials(ticker)
        if metrics:
            _cache_write(path, metrics)
            return metrics
        if attempt < 2:
            time.sleep(2 ** (attempt + 1))
    return None


def _stage1_fundamentals(tickers: list[str]) -> tuple[list[str], dict]:
    _set_progress(phase="stage1_fundamentals", total=len(tickers), current=0)
    survivors = []
    rej = {"market_cap": 0, "rev_growth": 0, "gross_margin": 0, "pe": 0, "no_data": 0}
    cached_hits = 0

    for i, ticker in enumerate(tickers):
        _set_progress(current=i + 1, current_ticker=ticker)

        path = os.path.join(_FUND_CACHE_DIR, f"{ticker}.json")
        is_cached = _cache_read(path, _FUND_TTL) is not None
        metrics = _get_fundamentals(ticker)
        if not is_cached:
            time.sleep(_FINNHUB_INTERVAL)
        else:
            cached_hits += 1

        if not metrics:
            rej["no_data"] += 1
            continue

        mc = metrics.get("marketCapitalization") or 0
        rev_g = metrics.get("revenueGrowthTTMYoy") or 0
        gm = metrics.get("grossMarginTTM") or 0
        pe = metrics.get("peNormalizedAnnual") or metrics.get("peTTM") or 0

        if mc < 5_000:
            rej["market_cap"] += 1
            continue
        if rev_g <= 0:
            rej["rev_growth"] += 1
            continue
        if gm < 15:
            rej["gross_margin"] += 1
            continue
        if pe > 100:
            rej["pe"] += 1
            continue

        survivors.append(ticker)

    logger.info(
        "Stage 1b fundamentals: %d → %d (%d cached, rej mc=%d rev=%d gm=%d pe=%d no_data=%d)",
        len(tickers), len(survivors), cached_hits,
        rej["market_cap"], rej["rev_growth"], rej["gross_margin"], rej["pe"], rej["no_data"],
    )
    return survivors, rej


# ── Stage 2: Full trigger scoring ─────────────────────────────────────────────

def _get_earnings_cached(ticker: str) -> int | None:
    path = os.path.join(_EARN_CACHE_DIR, f"{ticker}.json")
    cached = _cache_read(path, _EARN_TTL)
    if cached is not None:
        return cached.get("earnings_days")
    from services.finnhub_client import get_earnings_this_month
    try:
        days = get_earnings_this_month(ticker)
    except Exception:
        days = None
    _cache_write(path, {"earnings_days": days})
    return days


def _score_ticker(ticker: str, metrics: dict, snapshot_price: float | None = None) -> dict | None:
    """
    Score one ticker using pre-cached Finnhub metrics.
    snapshot_price: current price from Polygon batch snapshot (used for display only).
    Applies skip-MC logic: skip Monte Carlo when non_MC_earned + 2 < 6.
    """
    try:
        from services.trigger_service import _fetch_ma_data, _calculate_score
        from services.dcf_service import _mechanial_scenarios, _monte_carlo_dcf
        from services.discovery_engine import _wacc_from_beta, _run_dcf

        # ── Earnings ──────────────────────────────────────────────────────────
        earnings_days = _get_earnings_cached(ticker)
        has_near_earnings = earnings_days is not None and earnings_days <= 14

        # ── 50-day MA (Polygon) ───────────────────────────────────────────────
        ma_data = _fetch_ma_data(ticker)

        if ma_data and ma_data["crossover_5d"]:
            ma_score = 2
        elif ma_data and ma_data["above_ma"]:
            ma_score = 1
        else:
            ma_score = 0

        earnings_score = 0 if has_near_earnings else 1

        # ── DCF inputs from cached Finnhub data (no API call) ─────────────────
        # Finnhub marketCapitalization is in millions USD
        mc_val = metrics.get("marketCapitalization") or 0
        ps = metrics.get("psTTM") or 0
        if mc_val <= 0 or ps <= 0:
            return None

        revenue_0 = mc_val / ps

        fcf_margin_raw = (
            metrics.get("fcfMarginTTM") or
            metrics.get("freeCashFlowMarginTTM") or
            metrics.get("fcfMargin5Y") or 0
        )
        gm_pct = metrics.get("grossMarginTTM") or 40
        nm_pct = metrics.get("netProfitMarginTTM") or 0

        fcf_0 = max(
            fcf_margin_raw / 100,
            nm_pct / 100 * 0.85,
            gm_pct / 100 * 0.15,
        )

        beta = metrics.get("beta")
        dr = _wacc_from_beta(beta)

        d_for_scenarios = {
            "revenue_growth": metrics.get("revenueGrowthTTMYoy") or 0,
            "fcf_margin": fcf_margin_raw,
            "gross_margin": gm_pct,
            "net_margin": nm_pct,
        }
        cp = _mechanial_scenarios(d_for_scenarios)
        scenarios = {
            "bull": dict(g1=cp["bull"]["g1"], g2=cp["bull"]["g2"],
                         fm=cp["bull"]["fcf"], tg=cp["bull"].get("tg", 0.035)),
            "base": dict(g1=cp["base"]["g1"], g2=cp["base"]["g2"],
                         fm=cp["base"]["fcf"], tg=cp["base"].get("tg", 0.030)),
            "bear": dict(g1=cp["bear"]["g1"], g2=cp["bear"]["g2"],
                         fm=cp["bear"]["fcf"], tg=cp["bear"].get("tg", 0.020)),
        }

        dcf_result = _run_dcf(revenue_0, fcf_0, dr, scenarios, mc_val)

        bear_upside = dcf_result.get("bear_upside")
        base_upside = dcf_result.get("base_upside")

        bear_downside = abs(bear_upside) if (bear_upside is not None and bear_upside < 0) else 0
        bear_score = 1 if (bear_upside is not None and bear_downside < 30) else 0
        base_score = 1 if (base_upside is not None and base_upside > 20) else 0

        non_mc_earned = ma_score + earnings_score + bear_score + base_score

        # ── Skip MC if can't reach 7 ───────────────────────────────────────────
        mc_result: dict = {}
        if non_mc_earned + 2 >= 6:  # i.e., non_mc_earned >= 4
            shares_m = metrics.get("shareOutstanding") or 0
            mc_result = _monte_carlo_dcf(revenue_0, mc_val, shares_m, dr, scenarios)

        # ── Full score via _calculate_score ────────────────────────────────────
        dcf_for_score = {
            "dcf_bear_upside": bear_upside,
            "dcf_base_upside": base_upside,
            "monte_carlo": mc_result,
        }

        score, breakdown, action, suggested_size, blocked = _calculate_score(
            dcf_for_score, ma_data, earnings_days
        )

        current_price = snapshot_price  # from Polygon batch snapshot

        return {
            "ticker": ticker,
            "score": score,
            "action": action,
            "blocked": blocked,
            "suggested_size": suggested_size,
            "breakdown": breakdown,
            "ma_data": ma_data,
            "earnings_days": earnings_days,
            "current_price": current_price,
            "market_cap_b": round(mc_val / 1_000, 2),
            "dcf_base_upside": base_upside,
            "dcf_bear_upside": bear_upside,
            "revenue_growth_pct": round(metrics.get("revenueGrowthTTMYoy") or 0, 1),
            "gross_margin_pct": round(gm_pct, 1),
            "monte_carlo": mc_result,
            "non_mc_earned": non_mc_earned,
            "sector": metrics.get("_sector", ""),
            "name": metrics.get("_name", ticker),
        }
    except Exception as e:
        logger.warning("Score failed for %s: %s", ticker, e)
        return None


# ── Near-trigger message ──────────────────────────────────────────────────────

def _near_trigger_message(r: dict) -> str:
    bd = r.get("breakdown") or {}

    mc_bd = bd.get("monte_carlo") or {}
    if mc_bd.get("earned", 0) < 2:
        prob = (r.get("monte_carlo") or {}).get("prob_undervalued_pct")
        if prob is not None:
            return f"Needs MC ≥85% (currently {prob}%)"
        return "Needs stronger Monte Carlo probability"

    ma_bd = bd.get("ma") or {}
    if (ma_bd.get("earned") or 0) < 2:
        if (ma_bd.get("earned") or 0) == 0:
            return "Needs price above 50-day MA"
        return "Needs 50-day MA golden cross (above but no recent cross)"

    earn_bd = bd.get("earnings") or {}
    if (earn_bd.get("earned") or 0) == 0:
        days = r.get("earnings_days")
        return f"Earnings in {days}d — wait for post-earnings entry" if days else "Earnings risk window"

    bear_bd = bd.get("bear") or {}
    if (bear_bd.get("earned") or 0) == 0:
        return "Needs bear case downside <30%"

    base_bd = bd.get("base") or {}
    if (base_bd.get("earned") or 0) == 0:
        upside = r.get("dcf_base_upside")
        return f"Needs base case >20% upside (currently {upside:+.0f}%)" if upside else "Needs base case >20% upside"

    return "One criterion away from trigger"


# ── Result cache ──────────────────────────────────────────────────────────────

def _load_result_cache() -> dict | None:
    cached = _cache_read(_RESULT_CACHE, _RESULT_TTL)
    return cached


def _save_result_cache(data: dict) -> None:
    _cache_write(_RESULT_CACHE, data)


def _cache_timestamp() -> str | None:
    try:
        if not os.path.exists(_RESULT_CACHE):
            return None
        mtime = os.path.getmtime(_RESULT_CACHE)
        return datetime.fromtimestamp(mtime).isoformat()
    except Exception:
        return None


# ── Main scan ─────────────────────────────────────────────────────────────────

def run_top_rated_scan(force: bool = False) -> dict:
    """Run the full two-stage scan. Returns results dict."""
    with _scan_lock:
        if not force:
            cached = _load_result_cache()
            if cached:
                logger.info("Top Rated: returning cached results")
                return cached

        _ensure_dirs()
        _set_progress(
            status="running",
            phase="init",
            started_at=datetime.now().isoformat(),
            current=0, total=0, current_ticker="",
            stage1a_survivors=None,
            stage1b_survivors=None,
            stage2_scored=None,
        )

        try:
            universe = _load_universe()
            logger.info("Top Rated Scanner: %d tickers in universe", len(universe))
            _set_progress(universe_count=len(universe))

            # Stage 1a: Polygon price + volume (also captures snapshot prices)
            from services.polygon_client import get_snapshots_batch
            _set_progress(phase="stage1_price_volume", current=0, total=len(universe))
            try:
                snapshots = get_snapshots_batch(universe)
            except Exception as e:
                logger.warning("Polygon batch snapshot failed: %s — skipping Stage 1a", e)
                snapshots = {}

            polygon_available = bool(snapshots)
            if not polygon_available:
                # Polygon returned no data (market closed / API issue) — skip price/vol filter
                # and pass all tickers to Stage 1b so Finnhub fundamentals do the filtering.
                logger.info("Stage 1a: Polygon returned no snapshot data — passing all %d tickers to Stage 1b", len(universe))
                stage1a = list(universe)
                rej_pv = {"price": 0, "volume": 0, "no_data": len(universe)}
            else:
                stage1a = []
                rej_pv = {"price": 0, "volume": 0, "no_data": 0}
                for t in universe:
                    snap = snapshots.get(t)
                    if not snap:
                        rej_pv["no_data"] += 1
                        continue
                    # Use prev_close as fallback when market is closed (day.close = 0)
                    price = snap.get("price") or snap.get("prev_close") or 0
                    vol = snap.get("volume") or 0
                    if price < 15:
                        rej_pv["price"] += 1
                        continue
                    if vol > 0 and vol < 1_000_000:
                        rej_pv["volume"] += 1
                        continue
                    stage1a.append(t)

            logger.info(
                "Stage 1a: %d → %d (rej price=%d vol=%d no_data=%d)",
                len(universe), len(stage1a), rej_pv["price"], rej_pv["volume"], rej_pv["no_data"],
            )
            _set_progress(stage1a_survivors=len(stage1a))

            # Stage 1b: Finnhub fundamentals
            stage1b, rej_stats = _stage1_fundamentals(stage1a)
            _set_progress(stage1b_survivors=len(stage1b))

            # Stage 2: Full scoring
            _set_progress(phase="stage2_scoring", total=len(stage1b), current=0)
            scored = []
            skipped_mc_count = 0

            for i, ticker in enumerate(stage1b):
                _set_progress(current=i + 1, current_ticker=ticker)
                metrics = _get_fundamentals(ticker) or {}
                snap = snapshots.get(ticker) or {}
                snap_price = snap.get("price") or snap.get("prev_close")
                result = _score_ticker(ticker, metrics, snapshot_price=snap_price)
                if result is None:
                    continue
                nm = result.get("non_mc_earned", 0)
                if nm + 2 < 6:
                    skipped_mc_count += 1
                    continue
                scored.append(result)

            scored.sort(key=lambda x: x["score"], reverse=True)

            top_rated = [s for s in scored if s["score"] >= 6]
            near_trigger_raw = [s for s in scored if s["score"] == 5][:10]

            for s in near_trigger_raw:
                s["near_trigger_message"] = _near_trigger_message(s)

            output = {
                "scanned_at": datetime.now().isoformat(),
                "universe_count": len(universe),
                "stage1a_survivors": len(stage1a),
                "stage1b_survivors": len(stage1b),
                "stage2_scored": len(scored),
                "skipped_mc_count": skipped_mc_count,
                "top_rated": top_rated,
                "near_trigger": near_trigger_raw,
                "rejection_stats": rej_stats,
            }

            _save_result_cache(output)
            _set_progress(status="complete", phase="done", stage2_scored=len(scored))
            logger.info(
                "Top Rated Scan complete: %d top-rated, %d near-trigger",
                len(top_rated), len(near_trigger_raw),
            )
            return output

        except Exception as e:
            logger.error("Top Rated Scan failed: %s", e, exc_info=True)
            _set_progress(status="error", error=str(e))
            raise


def launch_scan_background(force: bool = False) -> None:
    t = threading.Thread(
        target=run_top_rated_scan,
        kwargs={"force": force},
        daemon=True,
        name="top-rated-scanner",
    )
    t.start()
    logger.info("Top Rated Scanner launched in background (force=%s)", force)
