from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/momentum", tags=["Momentum Alerts"])


@router.get("/alerts")
def get_alerts():
    """Return cached momentum alerts, starting a background scan if stale."""
    from services.momentum_scanner_service import (
        _cache_read, get_scan_status, launch_scan_background,
    )
    cached = _cache_read()
    if cached:
        return cached
    status = get_scan_status()
    if status.get("status") != "running":
        launch_scan_background(force=False)
    return {
        "alerts": [],
        "scanning": True,
        "message": "Scan started — poll /api/momentum/status for progress",
    }


@router.post("/refresh")
def refresh():
    """Force a fresh scan, ignoring the 6-hour cache."""
    from services.momentum_scanner_service import get_scan_status, launch_scan_background
    status = get_scan_status()
    if status.get("status") == "running":
        return {"status": "already_running", "message": "Scan already in progress"}
    launch_scan_background(force=True)
    return {"status": "started", "message": "Momentum scan launched in background"}


@router.get("/status")
def get_status():
    """Live progress for the current or last scan."""
    from services.momentum_scanner_service import get_scan_status, _cache_timestamp
    s = get_scan_status()
    s["last_cached_at"] = _cache_timestamp()
    return s


@router.get("/debug/{ticker}")
def debug_ticker(ticker: str):
    """Run all 3 momentum signals for a single ticker and return raw scores."""
    from services.polygon_client import get_close_prices
    from services.momentum_scanner_service import (
        _score_options_flow, _score_insider_cluster, _score_pre_earnings_drift,
    )
    t = ticker.upper().strip()

    # Get price from Polygon snapshot
    from services.polygon_client import get_snapshots_batch
    snaps = get_snapshots_batch([t])
    snap = snaps.get(t) or {}
    price = snap.get("price") or snap.get("prev_close") or 0
    if not price:
        raise HTTPException(status_code=404, detail=f"No price data for {t}")

    spy_closes = get_close_prices("SPY", days=100)
    options_score, options_detail = _score_options_flow(t, price)
    insider_score, insider_detail = _score_insider_cluster(t)
    drift_score, drift_detail = _score_pre_earnings_drift(t, spy_closes)

    return {
        "ticker": t,
        "price": price,
        "signals": {
            "options_flow":        {"score": options_score,  **options_detail},
            "insider_cluster":     {"score": insider_score,  **insider_detail},
            "pre_earnings_drift":  {"score": drift_score,    **drift_detail},
        },
        "total_score": options_score + insider_score + drift_score,
    }
