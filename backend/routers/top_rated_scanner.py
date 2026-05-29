from fastapi import APIRouter

router = APIRouter(prefix="/api/top-rated", tags=["Top Rated Scanner"])


@router.get("/results")
def get_results():
    """Return cached top-rated scan results, triggering a background scan if stale."""
    from services.top_rated_scanner_service import (
        _load_result_cache, get_scan_status, launch_scan_background,
    )
    cached = _load_result_cache()
    if cached:
        return cached
    status = get_scan_status()
    if status.get("status") != "running":
        launch_scan_background(force=False)
    return {
        "top_rated": [],
        "near_trigger": [],
        "scanning": True,
        "message": "Scan started — poll /api/top-rated/status for progress",
    }


@router.get("/status")
def get_status():
    """Live progress state for the current or last scan."""
    from services.top_rated_scanner_service import get_scan_status, _cache_timestamp
    status = get_scan_status()
    status["last_cached_at"] = _cache_timestamp()
    return status


@router.post("/refresh")
def refresh():
    """Force a fresh scan, ignoring the 24-hour cache."""
    from services.top_rated_scanner_service import get_scan_status, launch_scan_background
    status = get_scan_status()
    if status.get("status") == "running":
        return {"status": "already_running", "message": "Scan already in progress"}
    launch_scan_background(force=True)
    return {"status": "started", "message": "Top Rated scan launched in background"}
