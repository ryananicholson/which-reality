import json
import re
import threading
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import get_db
from models.wheel import WheelRecommendation, WheelPosition, WheelHistory, WheelStatus
from schemas.wheel import (
    WheelRecommendationSchema,
    WheelPositionSchema,
    AcceptWheelBody,
    UpdateStatusBody,
)

router = APIRouter()
logger = logging.getLogger(__name__)
_TICKER_RE = re.compile(r'^[A-Z]{1,5}$')


class CustomAnalyzeRequest(BaseModel):
    ticker: str

VALID_TRANSITIONS = {
    WheelStatus.put_active: [WheelStatus.assigned, WheelStatus.closed],
    WheelStatus.assigned: [WheelStatus.call_active, WheelStatus.closed],
    WheelStatus.call_active: [WheelStatus.assigned, WheelStatus.closed],
    WheelStatus.closed: [],
}


def _latest_wheel_batch(db: Session) -> List[WheelRecommendation]:
    latest = (
        db.query(WheelRecommendation.run_at)
        .order_by(desc(WheelRecommendation.run_at))
        .first()
    )
    if not latest:
        return []
    return (
        db.query(WheelRecommendation)
        .filter(WheelRecommendation.run_at == latest[0])
        .order_by(WheelRecommendation.rank)
        .all()
    )


@router.get("/recommendations")
def get_wheel_recommendations(db: Session = Depends(get_db)):
    from services.finnhub_client import get_earnings_this_month
    from services.iv_rank_service import get_iv_rank
    recs = _latest_wheel_batch(db)

    # Fetch IV rank concurrently for all tickers
    tickers = [rec.ticker for rec in recs]
    iv_rank_cache = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(get_iv_rank, t): t for t in set(tickers)}
        for fut in as_completed(futures, timeout=30):
            t = futures[fut]
            try:
                iv_rank_cache[t] = fut.result(timeout=10)
            except Exception:
                iv_rank_cache[t] = {}

    result = []
    for rec in recs:
        d = WheelRecommendationSchema.model_validate(rec).model_dump()
        try:
            d["earnings_days"] = get_earnings_this_month(rec.ticker)
        except Exception:
            d["earnings_days"] = None
        d["iv_rank"] = iv_rank_cache.get(rec.ticker, {})
        result.append(d)
    return result


@router.post("/recommendations/{rec_id}/accept", response_model=WheelPositionSchema)
def accept_wheel_recommendation(
    rec_id: int, body: AcceptWheelBody, db: Session = Depends(get_db)
):
    rec = db.get(WheelRecommendation, rec_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    if rec.accepted:
        raise HTTPException(status_code=400, detail="Already accepted")

    put_strike = body.put_strike or rec.put_strike
    put_expiry = body.put_expiry or rec.put_expiry or ""
    if not put_strike:
        raise HTTPException(status_code=400, detail="put_strike is required")

    position = WheelPosition(
        recommendation_id=rec.id,
        ticker=rec.ticker,
        status=WheelStatus.put_active,
        put_strike=put_strike,
        put_expiry=put_expiry,
        put_premium_rcvd=body.put_premium_rcvd or rec.put_premium,
    )
    db.add(position)
    rec.accepted = True
    rec.accepted_at = datetime.now(timezone.utc)
    db.flush()

    history = WheelHistory(
        position_id=position.id,
        from_status=None,
        to_status=WheelStatus.put_active,
        note="Position opened via Accept",
    )
    db.add(history)
    db.commit()
    db.refresh(position)
    return position


@router.get("/positions", response_model=List[WheelPositionSchema])
def get_wheel_positions(include_closed: bool = False, db: Session = Depends(get_db)):
    q = db.query(WheelPosition)
    if not include_closed:
        q = q.filter(WheelPosition.status != WheelStatus.closed)
    return q.order_by(desc(WheelPosition.put_opened_at)).all()


@router.get("/positions/{pos_id}", response_model=WheelPositionSchema)
def get_wheel_position(pos_id: int, db: Session = Depends(get_db)):
    pos = db.get(WheelPosition, pos_id)
    if not pos:
        raise HTTPException(status_code=404, detail="Position not found")
    return pos


@router.patch("/positions/{pos_id}/status", response_model=WheelPositionSchema)
def update_position_status(
    pos_id: int, body: UpdateStatusBody, db: Session = Depends(get_db)
):
    pos = db.get(WheelPosition, pos_id)
    if not pos:
        raise HTTPException(status_code=404, detail="Position not found")

    try:
        new_status = WheelStatus(body.new_status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {body.new_status}")

    allowed = VALID_TRANSITIONS.get(pos.status, [])
    if new_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from {pos.status} to {new_status}. Allowed: {[s.value for s in allowed]}",
        )

    old_status = pos.status
    pos.status = new_status
    now = datetime.now(timezone.utc)

    if new_status == WheelStatus.assigned:
        pos.assigned_at = body.assigned_at or now
        if pos.put_strike and pos.put_premium_rcvd:
            pos.cost_basis = round(pos.put_strike - pos.put_premium_rcvd, 4)
        # Trigger call suggestion in background
        threading.Thread(target=_generate_call_suggestion_bg, args=(pos_id,), daemon=True).start()

    elif new_status == WheelStatus.call_active:
        if body.call_strike:
            pos.call_strike = body.call_strike
        if body.call_expiry:
            pos.call_expiry = body.call_expiry
        if body.call_premium_rcvd:
            pos.call_premium_rcvd = body.call_premium_rcvd
        pos.call_opened_at = now

    elif new_status == WheelStatus.closed:
        pos.closed_at = now
        if body.total_pnl is not None:
            pos.total_pnl = body.total_pnl
        if body.notes:
            pos.notes = body.notes

    # If going back to assigned from call_active (call expired worthless), clear call fields
    if new_status == WheelStatus.assigned and old_status == WheelStatus.call_active:
        pos.call_strike = None
        pos.call_expiry = None
        pos.call_premium_rcvd = None
        pos.call_opened_at = None

    history = WheelHistory(
        position_id=pos.id,
        from_status=old_status,
        to_status=new_status,
        note=body.note,
    )
    db.add(history)
    db.commit()
    db.refresh(pos)
    return pos


@router.get("/positions/{pos_id}/call-suggestion")
def get_call_suggestion(pos_id: int, db: Session = Depends(get_db)):
    pos = db.get(WheelPosition, pos_id)
    if not pos:
        raise HTTPException(status_code=404, detail="Position not found")
    if pos.status not in (WheelStatus.assigned, WheelStatus.call_active):
        raise HTTPException(status_code=400, detail="Position must be assigned or call_active")
    return {
        "suggestion": json.loads(pos.call_suggestion) if pos.call_suggestion else None,
        "generated_at": pos.call_suggestion_at,
    }


@router.get("/positions/export")
def export_positions(db: Session = Depends(get_db)):
    """Export all wheel positions and their full history as JSON for backup purposes."""
    positions = db.query(WheelPosition).order_by(WheelPosition.put_opened_at).all()
    result = []
    for pos in positions:
        history = [
            {
                "from_status": h.from_status.value if h.from_status else None,
                "to_status": h.to_status.value,
                "note": h.note,
                "changed_at": h.changed_at.isoformat() if h.changed_at else None,
            }
            for h in pos.history
        ]
        result.append({
            "id": pos.id,
            "ticker": pos.ticker,
            "status": pos.status.value,
            "put_strike": pos.put_strike,
            "put_expiry": pos.put_expiry,
            "put_premium_rcvd": pos.put_premium_rcvd,
            "put_opened_at": pos.put_opened_at.isoformat() if pos.put_opened_at else None,
            "assigned_at": pos.assigned_at.isoformat() if pos.assigned_at else None,
            "cost_basis": pos.cost_basis,
            "shares": pos.shares,
            "call_strike": pos.call_strike,
            "call_expiry": pos.call_expiry,
            "call_premium_rcvd": pos.call_premium_rcvd,
            "call_opened_at": pos.call_opened_at.isoformat() if pos.call_opened_at else None,
            "closed_at": pos.closed_at.isoformat() if pos.closed_at else None,
            "total_pnl": pos.total_pnl,
            "notes": pos.notes,
            "history": history,
        })
    return {"exported_at": datetime.now(timezone.utc).isoformat(), "positions": result}


@router.post("/positions/{pos_id}/call-suggestion/refresh")
def refresh_call_suggestion(pos_id: int, db: Session = Depends(get_db)):
    pos = db.get(WheelPosition, pos_id)
    if not pos:
        raise HTTPException(status_code=404, detail="Position not found")
    threading.Thread(target=_generate_call_suggestion_bg, args=(pos_id,), daemon=True).start()
    return {"status": "queued"}


@router.get("/put-tiers/{ticker}")
def get_put_tiers(ticker: str):
    """Real options chain put tiers for a ticker (3 delta targets: ~0.45, ~0.30, ~0.16)."""
    ticker = ticker.strip().upper()
    if not _TICKER_RE.match(ticker):
        raise HTTPException(status_code=400, detail="Invalid ticker.")
    from services.stock_data import StockDataService
    tiers = StockDataService().get_put_tiers(ticker)
    if not tiers:
        raise HTTPException(status_code=503, detail=f"Could not fetch options chain for {ticker}.")
    return tiers


@router.post("/custom-analyze")
def custom_analyze_wheel(req: CustomAnalyzeRequest, db: Session = Depends(get_db)):
    """On-demand wheel strategy analysis for any ticker with real options chain data."""
    ticker = req.ticker.strip().upper()
    if not _TICKER_RE.match(ticker):
        raise HTTPException(status_code=400, detail="Invalid ticker. Use 1-5 letters (e.g. AAPL).")

    from services.stock_data import StockDataService
    from services.news_scraper import NewsScraper
    from services.claude_analyst import ClaudeAnalyst

    stock_data = StockDataService()
    scraper = NewsScraper()
    analyst = ClaudeAnalyst()

    tech = stock_data.get_price_and_technicals(ticker)
    current_price = tech.get("price")
    if not current_price:
        raise HTTPException(status_code=404,
                            detail=f"No price data for {ticker}. Check the symbol and try again.")

    put_tiers = stock_data.get_put_tiers(ticker)
    if not put_tiers:
        raise HTTPException(status_code=503,
                            detail=f"Could not fetch options chain for {ticker}. "
                                   "Check the symbol and try again.")

    try:
        fund_map = stock_data.get_fundamentals([ticker])
        fundamentals = fund_map.get(ticker) or {}
    except Exception:
        fundamentals = {}

    try:
        news_items = scraper.fetch_all([ticker])
        news_bullets = "\n".join(
            f"- [{it.ticker or 'MARKET'}] {it.source}: {it.headline}"
            for it in news_items[:20]
        ) or "No recent news available."
    except Exception:
        news_bullets = "News unavailable — base analysis on technicals."

    try:
        result = analyst.analyze_wheel_custom(
            ticker=ticker,
            current_price=current_price,
            put_tiers=put_tiers,
            fundamentals=fundamentals,
            technicals=tech,
            news_bullets=news_bullets,
        )
        result["ticker"] = ticker
        result["current_price"] = current_price
        result["data_source"] = put_tiers.get("data_source", "last_trade")
        result["put_tiers_raw"] = put_tiers
        return result
    except Exception as e:
        logger.error("Wheel custom analysis failed for %s: %s", ticker, e)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/positions/{pos_id}/roll-alert")
def get_roll_alert(pos_id: int, db: Session = Depends(get_db)):
    """
    Check if the stock has dropped close to the put strike.
    Uses Finnhub for price (reliable). Only relevant for put_active positions.
    """
    pos = db.get(WheelPosition, pos_id)
    if not pos:
        raise HTTPException(status_code=404, detail="Position not found")
    if pos.status != WheelStatus.put_active:
        return {"alert_level": "none", "current_price": None, "pct_from_strike": None}

    from services.finnhub_client import get_quote
    q = get_quote(pos.ticker)
    current_price = q.get("c") or q.get("pc")  # current or prev close
    if not current_price:
        return {"alert_level": "none", "current_price": None, "pct_from_strike": None,
                "message": "Price unavailable"}

    current_price = float(current_price)
    pct_from_strike = round((current_price - pos.put_strike) / pos.put_strike * 100, 1)

    if pct_from_strike > 5:
        level = "none"
        message = None
    elif pct_from_strike > 2:
        level = "warning"
        message = (
            f"{pos.ticker} is ${round(current_price,2)} — only {pct_from_strike}% above your "
            f"${pos.put_strike} strike. Getting close — worth monitoring."
        )
    else:
        level = "danger"
        if pct_from_strike <= 0:
            message = (
                f"⚠ {pos.ticker} is ${round(current_price,2)} — below your ${pos.put_strike} strike. "
                "Assignment is likely. Consider rolling to avoid owning shares at a loss."
            )
        else:
            message = (
                f"⚠ {pos.ticker} is ${round(current_price,2)} — only {pct_from_strike}% above your "
                f"${pos.put_strike} strike. High assignment risk. Consider rolling now."
            )

    return {
        "alert_level": level,
        "current_price": current_price,
        "put_strike": pos.put_strike,
        "pct_from_strike": pct_from_strike,
        "message": message,
    }


@router.post("/positions/{pos_id}/roll-suggestion")
def get_roll_suggestion(pos_id: int, db: Session = Depends(get_db)):
    """
    Generate a specific roll recommendation using current options chain + Claude.
    Uses yfinance for options chain (no free Finnhub alternative).
    """
    pos = db.get(WheelPosition, pos_id)
    if not pos:
        raise HTTPException(status_code=404, detail="Position not found")
    if pos.status != WheelStatus.put_active:
        raise HTTPException(status_code=400, detail="Roll suggestions only apply to put_active positions")

    from services.finnhub_client import get_quote
    from services.stock_data import StockDataService
    from services.claude_analyst import ClaudeAnalyst

    # Current price via Finnhub
    q = get_quote(pos.ticker)
    current_price = float(q.get("c") or q.get("pc") or 0)
    if not current_price:
        raise HTTPException(status_code=503, detail="Could not fetch current price")

    # Options chain via yfinance
    stock_data = StockDataService()
    put_tiers = stock_data.get_put_tiers(pos.ticker)
    if not put_tiers:
        raise HTTPException(
            status_code=503,
            detail="Options chain unavailable. Markets may be closed — try again during trading hours."
        )

    analyst = ClaudeAnalyst()
    try:
        result = analyst.suggest_roll(
            ticker=pos.ticker,
            current_price=current_price,
            put_strike=pos.put_strike,
            put_expiry=pos.put_expiry,
            premium_received=pos.put_premium_rcvd,
            put_tiers=put_tiers,
        )
        result["current_price"] = current_price
        result["data_source"] = put_tiers.get("data_source", "last_trade")
        return result
    except Exception as e:
        logger.error("Roll suggestion failed for pos %d: %s", pos_id, e)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")


@router.post("/refresh")
def refresh_wheel():
    def _run():
        from database import SessionLocal
        from services.wheel_engine import WheelEngine
        s = SessionLocal()
        try:
            WheelEngine(s).run()
        finally:
            s.close()

    threading.Thread(target=_run, daemon=True).start()
    return {"status": "queued", "message": "Wheel analysis started in background"}


def _generate_call_suggestion_bg(pos_id: int) -> None:
    from database import SessionLocal
    from services.wheel_engine import WheelEngine
    from datetime import datetime, timezone
    s = SessionLocal()
    try:
        pos = s.get(WheelPosition, pos_id)
        if not pos:
            return
        engine = WheelEngine(s)
        suggestion = engine.generate_call_suggestion(pos)
        if suggestion:
            pos.call_suggestion = suggestion
            pos.call_suggestion_at = datetime.now(timezone.utc)
            s.commit()
    except Exception as e:
        logger.error("Background call suggestion error for pos %d: %s", pos_id, e)
    finally:
        s.close()
