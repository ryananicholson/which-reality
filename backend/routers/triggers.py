from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/triggers", tags=["Stock Triggers"])


@router.get("/{ticker}")
def run_trigger_analysis(ticker: str):
    """
    Full trigger analysis for a ticker: DCF + Monte Carlo + 50-day MA + earnings
    calendar → trigger score (0-8) and action recommendation.
    """
    try:
        from services.trigger_service import analyze_trigger
        return analyze_trigger(ticker)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Trigger analysis failed: {e}")
