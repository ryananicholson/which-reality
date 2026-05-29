from fastapi import APIRouter

router = APIRouter(prefix="/api/market", tags=["Market Context"])


@router.get("/context")
def get_market_context(refresh: bool = False):
    from services.market_context import get_market_context as _get
    return _get(force_refresh=refresh)
