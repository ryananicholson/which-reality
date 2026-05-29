import logging
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/flow", tags=["Options Flow"])
logger = logging.getLogger(__name__)


@router.get("/scan")
def scan_options_flow():
    """Scan options chains for unusual volume vs open interest and return AI-interpreted alerts."""
    try:
        from services.options_flow_engine import run_flow_scan
        result = run_flow_scan()
        if result.get("error") and not result.get("alerts"):
            raise HTTPException(status_code=503, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Options flow scan failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Flow scan failed: {str(e)}")


@router.get("/debug")
def debug_options_api(ticker: str = "SPY"):
    """Return raw Polygon options snapshot data for one ticker — for diagnosing API issues."""
    try:
        from datetime import date, timedelta
        from services.polygon_client import _client
        import yfinance as yf

        # Get price first so we can filter to ATM strikes
        yfprice = None
        try:
            yfprice = float(yf.Ticker(ticker).fast_info.last_price or 0)
        except Exception:
            pass

        c = _client()
        today = date.today()
        params = {
            "expiration_date.gte": today.isoformat(),
            "expiration_date.lte": (today + timedelta(days=30)).isoformat(),
            "limit": 10,
        }
        if yfprice and yfprice > 0:
            params["strike_price.gte"] = round(yfprice * 0.85, 2)
            params["strike_price.lte"] = round(yfprice * 1.15, 2)
        snapshots = list(c.list_snapshot_options_chain(ticker, params=params))

        sample = []
        for snap in snapshots[:5]:
            d = snap.details
            sample.append({
                "ticker": ticker,
                "contract_type": getattr(d, "contract_type", None) if d else None,
                "strike": getattr(d, "strike_price", None) if d else None,
                "expiry": str(getattr(d, "expiration_date", None)) if d else None,
                "underlying_asset_price": float(snap.underlying_asset.price) if snap.underlying_asset and snap.underlying_asset.price else None,
                "day_volume": int(snap.day.volume or 0) if snap.day else None,
                "day_vwap": float(snap.day.vwap or 0) if snap.day else None,
                "open_interest": snap.open_interest,
                "implied_volatility": snap.implied_volatility,
                "last_quote_bid": float(snap.last_quote.bid or 0) if snap.last_quote else None,
                "last_quote_ask": float(snap.last_quote.ask or 0) if snap.last_quote else None,
                "last_quote_midpoint": float(snap.last_quote.midpoint or 0) if snap.last_quote else None,
                "last_trade_price": float(snap.last_trade.price or 0) if snap.last_trade else None,
                "greeks_delta": float(snap.greeks.delta) if snap.greeks and snap.greeks.delta is not None else None,
            })

        return {
            "ticker": ticker,
            "total_snapshots_returned": len(snapshots),
            "yfinance_price": yfprice,
            "sample_contracts": sample,
        }
    except Exception as e:
        logger.error("debug endpoint failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
