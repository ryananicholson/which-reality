from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/dcf", tags=["DCF Valuation"])


@router.get("/{ticker}")
def run_dcf(ticker: str):
    """
    Full DCF analysis for a single ticker.
    Fetches fundamentals from Finnhub, derives CAPM WACC from beta,
    computes reverse DCF (implied growth priced in), calls Claude to set
    bear/base/bull scenario parameters, and returns per-share price targets.
    """
    try:
        from services.dcf_service import analyze
        return analyze(ticker)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DCF analysis failed: {e}")
