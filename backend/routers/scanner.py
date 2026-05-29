import logging

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/scanner", tags=["Day Trade Scanner"])
logger = logging.getLogger(__name__)


@router.get("/market-status")
def market_status():
    """Current US equity market trading status."""
    from config import settings
    if not settings.polygon_api_key:
        raise HTTPException(status_code=503, detail="POLYGON_API_KEY is not configured.")
    try:
        from services.polygon_client import get_market_status
        return get_market_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scan")
def run_scan():
    """Scan top movers via Massive and return Claude's high-confidence day trade plays."""
    from config import settings
    if not settings.polygon_api_key:
        raise HTTPException(
            status_code=503,
            detail="POLYGON_API_KEY is not configured. Add it to your Render environment variables.",
        )
    try:
        from services.scanner_engine import run_scan as _run
        result = _run()
        if result.get("error") and not result.get("plays"):
            raise HTTPException(status_code=503, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Day trade scan failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")
