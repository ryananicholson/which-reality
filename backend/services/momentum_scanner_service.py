"""
Momentum Alerts Convergence Scanner — finds S&P 500 + Nasdaq 100 stocks
with 3+ independent signals firing in the same 21-day rolling window.

Signals (0-2 pts each, max 6):
  Signal 1: Unusual Options Flow   — Polygon options chain snapshot
  Signal 2: Insider Cluster Buying — Finnhub insider transactions (21d)
  Signal 3: Pre-Earnings Drift     — Price vs SPY outperformance into earnings

Convergence threshold : 3+ points
Cache TTL             : 6 hours  (/tmp/cache_momentum_scan.json)
Results returned      : top 10 by score
"""
import json
import logging
import os
import threading
import time
from datetime import date, datetime, timedelta, timezone

logger = logging.getLogger(__name__)

_CACHE_FILE = "/tmp/cache_momentum_scan.json"
_CACHE_TTL = 6 * 3600

_progress: dict = {
    "status": "idle",
    "phase": None,
    "current": 0,
    "total": 0,
    "current_ticker": "",
    "started_at": None,
}
_progress_lock = threading.Lock()
_scan_lock = threading.Lock()


def _load_universe() -> list:
    from services.top_rated_scanner_service import _load_universe as _trs_load
    return _trs_load()


def _cache_read() -> dict | None:
    try:
        if not os.path.exists(_CACHE_FILE):
            return None
        with open(_CACHE_FILE) as f:
            data = json.load(f)
        if time.time() - data.get("cached_at", 0) > _CACHE_TTL:
            return None
        return data
    except Exception:
        return None


def _cache_write(data: dict) -> None:
    try:
        data["cached_at"] = time.time()
        with open(_CACHE_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logger.warning("Momentum cache write failed: %s", e)


def _cache_timestamp() -> str | None:
    try:
        with open(_CACHE_FILE) as f:
            d = json.load(f)
        ts = d.get("cached_at")
        if ts:
            return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except Exception:
        pass
    return None


def _set_progress(**kwargs) -> None:
    with _progress_lock:
        _progress.update(kwargs)


def get_scan_status() -> dict:
    with _progress_lock:
        return dict(_progress)


# ── Signal 1: Unusual Options Flow ───────────────────────────────────────────

def _score_options_flow(ticker: str, price: float) -> tuple:
    """Score unusual options flow (0-2 pts). Counts OTM call contracts where vol/OI >= 2.0."""
    detail = {"unusual_contracts": 0, "total_notional": 0, "dominant_type": None}
    try:
        if price <= 0:
            return 0, detail
        from services.polygon_client import get_options_chain_snapshot
        snaps = get_options_chain_snapshot(
            ticker, dte_max=21, near_price=price, strike_pct_range=0.15
        )
        if not snaps:
            return 0, detail

        today = date.today()
        unusual = []
        call_notional = 0
        put_notional = 0

        for snap in snaps:
            try:
                d = snap.details
                if not d:
                    continue
                opt_type = (d.contract_type or "").lower()
                if opt_type not in ("call", "put"):
                    continue
                expiry_str = d.expiration_date
                if not expiry_str:
                    continue
                dte = (date.fromisoformat(str(expiry_str)) - today).days
                if dte < 0 or dte > 21:
                    continue

                volume = int(snap.day.volume or 0) if snap.day else 0
                if volume < 100:
                    continue
                oi = int(snap.open_interest or 0)
                if oi == 0:
                    vol_oi = 99.0
                else:
                    vol_oi = volume / oi
                    if vol_oi < 2.0:
                        continue

                mid = 0.0
                if snap.last_quote:
                    bid = float(snap.last_quote.bid or 0)
                    ask = float(snap.last_quote.ask or 0)
                    mid = (bid + ask) / 2 if bid > 0 and ask > 0 else 0
                if mid <= 0 and snap.last_trade and snap.last_trade.price:
                    mid = float(snap.last_trade.price or 0)
                notional = round(volume * mid * 100) if mid > 0 else 0

                unusual.append({"type": opt_type, "notional": notional})
                if opt_type == "call":
                    call_notional += notional
                else:
                    put_notional += notional
            except Exception:
                continue

        n = len(unusual)
        total_notional = call_notional + put_notional
        dominant = "call" if call_notional >= put_notional else "put"
        detail = {
            "unusual_contracts": n,
            "total_notional": total_notional,
            "dominant_type": dominant if n > 0 else None,
        }

        if n >= 3:
            return 2, detail
        if n >= 1:
            return 1, detail
        return 0, detail
    except Exception as e:
        logger.debug("options_flow signal failed for %s: %s", ticker, e)
        return 0, detail


# ── Signal 2: Insider Cluster Buying ─────────────────────────────────────────

def _score_insider_cluster(ticker: str) -> tuple:
    """Score insider cluster buying (0-2 pts) in the last 21 days."""
    detail = {"distinct_buyers": 0, "net_change": 0}
    try:
        from services.finnhub_client import get_insider_sentiment
        result = get_insider_sentiment(ticker, days=21)
        if not result:
            return 0, detail
        buyers = result.get("insiders_buying", 0)
        net = result.get("net_change", 0)
        detail = {"distinct_buyers": buyers, "net_change": net}
        if buyers >= 2 and net > 0:
            return 2, detail
        if buyers >= 1 and net > 0:
            return 1, detail
        return 0, detail
    except Exception as e:
        logger.debug("insider_cluster signal failed for %s: %s", ticker, e)
        return 0, detail


# ── Signal 3: Pre-Earnings Drift ─────────────────────────────────────────────

def _score_pre_earnings_drift(ticker: str, spy_closes: list) -> tuple:
    """Score pre-earnings momentum drift (0-2 pts). Only active 14-42 days before earnings."""
    detail = {"days_to_earnings": None, "ticker_return_21d": None, "spy_return_21d": None, "alpha": None}
    try:
        from services.finnhub_client import _get_client as _fh_client
        today = date.today()
        end = today + timedelta(days=42)
        cal = _fh_client().earnings_calendar(
            _from=today.strftime("%Y-%m-%d"),
            to=end.strftime("%Y-%m-%d"),
            symbol=ticker,
        )
        earnings_list = sorted(
            (cal or {}).get("earningsCalendar", []),
            key=lambda e: e.get("date", ""),
        )
        days_to_earnings = None
        for e in earnings_list:
            try:
                d = datetime.strptime(e["date"], "%Y-%m-%d").date()
                diff = (d - today).days
                if diff >= 0:
                    days_to_earnings = diff
                    break
            except Exception:
                pass

        # Only active 14-42 days before earnings (enforced after taking nearest date)
        if days_to_earnings is None or days_to_earnings < 14:
            return 0, detail

        detail["days_to_earnings"] = days_to_earnings

        from services.polygon_client import get_close_prices
        closes = get_close_prices(ticker, days=100)
        if len(closes) < 22 or len(spy_closes) < 22:
            return 0, detail

        ticker_return = (closes[-1] - closes[-22]) / closes[-22] * 100
        spy_return = (spy_closes[-1] - spy_closes[-22]) / spy_closes[-22] * 100
        alpha = round(ticker_return - spy_return, 2)

        detail.update({
            "ticker_return_21d": round(ticker_return, 2),
            "spy_return_21d": round(spy_return, 2),
            "alpha": alpha,
        })

        if alpha >= 5.0:
            return 2, detail
        if alpha >= 2.0:
            return 1, detail
        return 0, detail

    except Exception as e:
        logger.debug("pre_earnings_drift signal failed for %s: %s", ticker, e)
        return 0, detail


# ── Per-ticker orchestration ──────────────────────────────────────────────────

def _score_ticker(ticker: str, price: float, spy_closes: list) -> dict | None:
    try:
        options_score, options_detail = _score_options_flow(ticker, price)
        time.sleep(0.2)

        insider_score, insider_detail = _score_insider_cluster(ticker)
        time.sleep(1.2)  # Finnhub rate-limit gap

        drift_score, drift_detail = _score_pre_earnings_drift(ticker, spy_closes)

        total_score = options_score + insider_score + drift_score
        convergence = total_score >= 3

        return {
            "ticker": ticker,
            "price": round(price, 2),
            "total_score": total_score,
            "convergence": convergence,
            "signals": {
                "options_flow":       {"score": options_score,  **options_detail},
                "insider_cluster":    {"score": insider_score,  **insider_detail},
                "pre_earnings_drift": {"score": drift_score,    **drift_detail},
            },
        }
    except Exception as e:
        logger.debug("_score_ticker failed for %s: %s", ticker, e)
        return None


# ── Main scan ─────────────────────────────────────────────────────────────────

def run_momentum_scan(force: bool = False) -> dict:
    with _scan_lock:
        if not force:
            cached = _cache_read()
            if cached:
                logger.info("Momentum scan: returning cached results")
                return cached

        _set_progress(
            status="running", phase="init", current=0, total=0,
            current_ticker="", started_at=datetime.now().isoformat(),
        )
        try:
            import random
            universe = _load_universe()
            random.shuffle(universe)  # shuffle so partial runs aren't alphabet-biased
            _set_progress(phase="stage1_price_volume", total=len(universe))

            from services.polygon_client import get_snapshots_batch
            BATCH_SIZE = 500
            price_map = {}
            for i in range(0, len(universe), BATCH_SIZE):
                batch = universe[i:i + BATCH_SIZE]
                snaps = get_snapshots_batch(batch)
                for t, s in snaps.items():
                    price = s.get("price") or s.get("prev_close") or 0
                    vol = s.get("volume") or 0
                    if price >= 10 and (vol == 0 or vol >= 500_000):
                        price_map[t] = price

            logger.info(
                "Momentum Stage 1a: %d → %d tickers after price/vol filter",
                len(universe), len(price_map),
            )

            # If Polygon returned nothing (market closed), use a random 150-ticker sample
            # so the scan completes in ~5 min instead of timing out on the full universe
            if not price_map:
                logger.info("Momentum: Polygon returned no snapshot data — sampling 150 tickers")
                sample = universe[:150]  # already shuffled above
                price_map = {t: 0.0 for t in sample}

            _set_progress(phase="scoring", total=len(price_map), current=0)

            from services.polygon_client import get_close_prices
            spy_closes = get_close_prices("SPY", days=100)

            results = []
            for i, (ticker, price) in enumerate(price_map.items()):
                _set_progress(current=i + 1, current_ticker=ticker)
                try:
                    r = _score_ticker(ticker, price, spy_closes)
                    if r:
                        results.append(r)
                except Exception as e:
                    logger.debug("Score failed for %s: %s", ticker, e)

            results.sort(key=lambda x: x["total_score"], reverse=True)
            top = results[:10]

            output = {
                "scanned_at": datetime.now().isoformat(),
                "universe_count": len(universe),
                "stage1_survivors": len(price_map),
                "total_scored": len(results),
                "alerts": top,
            }
            _cache_write(output)
            _set_progress(status="complete", phase="done")
            logger.info(
                "Momentum scan complete: %d scored, %d alerts returned",
                len(results), len(top),
            )
            return output

        except Exception as e:
            logger.error("Momentum scan failed: %s", e, exc_info=True)
            _set_progress(status="error", error=str(e), phase="error")
            raise


def launch_scan_background(force: bool = False) -> None:
    t = threading.Thread(
        target=run_momentum_scan,
        kwargs={"force": force},
        daemon=True,
        name="momentum-scanner",
    )
    t.start()
    logger.info("Momentum scanner launched in background (force=%s)", force)
