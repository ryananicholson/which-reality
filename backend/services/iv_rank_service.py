"""
IV Rank and IV Percentile.
IV Rank > 50 → premium is historically rich → good for selling (wheel, covered calls)
IV Rank < 25 → premium is historically cheap → avoid selling
"""
import logging
import math

logger = logging.getLogger(__name__)


def get_iv_rank(ticker: str) -> dict:
    try:
        from services.polygon_client import get_close_prices, get_options_chain_snapshot, get_ticker_snapshot

        closes = get_close_prices(ticker, days=320)
        if len(closes) < 60:
            return _empty()

        # Build rolling 30-day HV series
        hv_series = []
        for i in range(30, len(closes)):
            hv = _hv(closes[i - 30:i])
            if hv is not None:
                hv_series.append(hv)

        if not hv_series:
            return _empty()

        current_hv = hv_series[-1]

        # Try live ATM IV from Polygon options snapshot
        current_iv = current_hv
        try:
            snap = get_ticker_snapshot(ticker)
            price = snap.get("price") or 0
            if price > 0:
                snaps = get_options_chain_snapshot(ticker, dte_max=45, near_price=price, strike_pct_range=0.04)
                best_diff = float("inf")
                for s in (snaps or []):
                    if not s.details or (s.details.contract_type or "").lower() != "call":
                        continue
                    if not s.implied_volatility:
                        continue
                    diff = abs(float(s.details.strike_price or 0) - price)
                    if diff < best_diff:
                        best_diff = diff
                        current_iv = float(s.implied_volatility)
        except Exception:
            pass

        hv_52w = hv_series[-252:] if len(hv_series) >= 252 else hv_series
        iv_max = max(hv_52w)
        iv_min = min(hv_52w)

        iv_rank = round((current_iv - iv_min) / (iv_max - iv_min) * 100, 1) if iv_max > iv_min else 50.0
        iv_rank = max(0.0, min(100.0, iv_rank))
        iv_percentile = round(sum(1 for h in hv_52w if h < current_iv) / len(hv_52w) * 100, 1)

        if iv_rank >= 50:
            label, signal = "high", "Rich premium — ideal for selling"
        elif iv_rank >= 25:
            label, signal = "normal", "Normal premium"
        else:
            label, signal = "low", "Cheap premium — avoid selling"

        return {
            "iv_rank": iv_rank,
            "iv_percentile": iv_percentile,
            "current_iv_pct": round(current_iv * 100, 1),
            "iv_52w_high_pct": round(iv_max * 100, 1),
            "iv_52w_low_pct": round(iv_min * 100, 1),
            "label": label,
            "signal": signal,
        }
    except Exception as e:
        logger.warning("get_iv_rank failed for %s: %s", ticker, e)
        return _empty()


def _hv(closes: list) -> float | None:
    if len(closes) < 2:
        return None
    try:
        lr = [math.log(closes[i] / closes[i-1]) for i in range(1, len(closes)) if closes[i] > 0 and closes[i-1] > 0]
        if len(lr) < 5:
            return None
        mean = sum(lr) / len(lr)
        var = sum((r - mean) ** 2 for r in lr) / max(len(lr) - 1, 1)
        hv = math.sqrt(var * 252)
        return hv if 0 < hv < 5.0 else None
    except Exception:
        return None


def _empty() -> dict:
    return {"iv_rank": None, "iv_percentile": None, "current_iv_pct": None,
            "iv_52w_high_pct": None, "iv_52w_low_pct": None, "label": None, "signal": None}
