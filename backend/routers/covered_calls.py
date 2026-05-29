import re
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/covered-calls", tags=["Covered Calls"])
logger = logging.getLogger(__name__)
_TICKER_RE = re.compile(r'^[A-Z]{1,6}$')


class CoveredCallRequest(BaseModel):
    ticker: str
    cost_basis: float | None = None


@router.post("/analyze")
def analyze_covered_calls(req: CoveredCallRequest):
    """
    Generate three weekly covered call recommendations for a ticker the user owns 100 shares of.
    Tiers: aggressive (high premium, likely called away), balanced, conservative (keeps shares).
    """
    ticker = req.ticker.strip().upper()
    if not _TICKER_RE.match(ticker):
        raise HTTPException(status_code=400, detail="Invalid ticker. Use 1-6 letters (e.g. SCHD, QQQM).")

    from services.stock_data import StockDataService
    from services.claude_analyst import ClaudeAnalyst
    from services.iv_rank_service import get_iv_rank

    stock_data = StockDataService()
    analyst = ClaudeAnalyst()

    tech = stock_data.get_price_and_technicals(ticker)
    tech_price = tech.get("price")
    if not tech_price:
        raise HTTPException(
            status_code=404,
            detail=f"No price data found for {ticker}. Check the symbol and try again.",
        )

    call_tiers = stock_data.get_call_tiers(ticker)
    if not call_tiers:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Could not fetch options data for {ticker}. "
                "Possible reasons: this ETF/stock has no listed options, "
                "yfinance is temporarily rate-limited, or all near-term strikes have zero volume. "
                "Try a different ticker or wait a few minutes and try again."
            ),
        )

    # Prefer the live price from call_tiers (fast_info / Polygon) over the daily-close from history
    current_price = call_tiers.get("current_price") or tech_price

    try:
        result = analyst.suggest_covered_calls(
            ticker=ticker,
            current_price=current_price,
            call_tiers=call_tiers,
            cost_basis=req.cost_basis,
        )
        result["ticker"] = ticker
        result["current_price"] = current_price
        result["data_source"] = call_tiers.get("data_source", "last_trade")
        result["expiry"] = call_tiers.get("expiry")
        result["dte"] = call_tiers.get("dte")
        result["atm_iv_pct"] = call_tiers.get("atm_iv_pct")
        result["options_type"] = call_tiers.get("options_type", "weekly")
        result["iv_rank"] = get_iv_rank(ticker)
        return result
    except Exception as e:
        logger.error("Covered call analysis failed for %s: %s", ticker, e)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
