from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/advanced-scanner", tags=["Advanced Scanner"])


@router.get("/status/{scan_type}")
def scan_status(scan_type: str):
    if scan_type not in ("dividend", "movers"):
        raise HTTPException(status_code=400, detail="scan_type must be 'dividend' or 'movers'")
    from services.advanced_scanner_service import get_scan_status, _cache_timestamp
    status = get_scan_status(scan_type)
    status["last_cached_at"] = _cache_timestamp(scan_type)
    return status


@router.get("/dividend")
def get_dividend_results():
    """Return cached dividend scan results, or trigger a fresh scan if cache is stale."""
    from services.advanced_scanner_service import _load_cache, launch_scan_background, get_scan_status
    cached = _load_cache("dividend")
    if cached:
        return cached
    status = get_scan_status("dividend")
    if not status["running"]:
        launch_scan_background("dividend")
    return {"results": [], "scanning": True, "mode": "dividend",
            "message": "Scan started — poll /api/advanced-scanner/status/dividend for progress"}


@router.get("/movers")
def get_mover_results():
    """Return cached big mover scan results, or trigger a fresh scan if cache is stale."""
    from services.advanced_scanner_service import _load_cache, launch_scan_background, get_scan_status
    cached = _load_cache("movers")
    if cached:
        return cached
    status = get_scan_status("movers")
    if not status["running"]:
        launch_scan_background("movers")
    return {"results": [], "scanning": True, "mode": "movers",
            "message": "Scan started — poll /api/advanced-scanner/status/movers for progress"}


@router.post("/refresh/{scan_type}")
def refresh_scan(scan_type: str):
    """Force a fresh scan, ignoring cache."""
    if scan_type not in ("dividend", "movers"):
        raise HTTPException(status_code=400, detail="scan_type must be 'dividend' or 'movers'")
    from services.advanced_scanner_service import launch_scan_background, get_scan_status
    status = get_scan_status(scan_type)
    if status["running"]:
        return {"status": "already_running", "message": f"{scan_type} scan is already in progress"}
    launch_scan_background(scan_type)
    return {"status": "started", "message": f"{scan_type} scan launched in background"}


@router.get("/debug/{ticker}")
def debug_fundamentals(ticker: str):
    """Return raw Finnhub metrics for a ticker — used to diagnose pre-filter issues."""
    from services.finnhub_client import get_basic_financials
    metrics = get_basic_financials(ticker.upper())
    # Return the fields relevant to scanner pre-filters
    fields = [
        "dividendYieldIndicatedAnnual", "currentDividendYieldTTM", "dividendYield5Y",
        "dividendPerShareAnnual", "dividendPerShareTTM",
        "payoutRatioTTM",
        "revenueGrowthTTMYoy", "revenueGrowth3M",
        "grossMarginTTM", "marketCapitalization",
        "10DayAverageTradingVolumeMillion", "3MonthAverageTradingVolumeMillion",
        "psTTM", "52WeekHigh", "beta",
    ]
    return {
        "ticker": ticker.upper(),
        "raw_metrics": {k: metrics.get(k) for k in fields},
        "all_keys_count": len(metrics),
    }
