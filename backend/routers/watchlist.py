import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models.watchlist import WatchlistItem

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/watchlist", tags=["Watchlist"])

_TICKER_RE = re.compile(r"^[A-Z]{1,5}$")


class AddBody(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=5)
    notes: str = Field("", max_length=500)


@router.get("")
def list_watchlist(db: Session = Depends(get_db)):
    items = db.query(WatchlistItem).order_by(WatchlistItem.added_at.desc()).all()
    return [_serialize(i) for i in items]


@router.post("")
def add_ticker(body: AddBody, db: Session = Depends(get_db)):
    ticker = body.ticker.strip().upper()
    if not _TICKER_RE.match(ticker):
        raise HTTPException(400, "Invalid ticker symbol")

    existing = db.query(WatchlistItem).filter(WatchlistItem.ticker == ticker).first()
    if existing:
        raise HTTPException(409, f"{ticker} is already on your watchlist")

    item = WatchlistItem(ticker=ticker, notes=body.notes or None)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize(item)


@router.delete("/{ticker}")
def remove_ticker(ticker: str, db: Session = Depends(get_db)):
    ticker = ticker.upper()
    item = db.query(WatchlistItem).filter(WatchlistItem.ticker == ticker).first()
    if not item:
        raise HTTPException(404, f"{ticker} not found in watchlist")
    db.delete(item)
    db.commit()
    return {"deleted": ticker}


@router.post("/{ticker}/quick-score")
def quick_score_ticker(ticker: str):
    """Score any ticker without requiring it to be on the watchlist — no DB writes."""
    ticker = ticker.upper()
    if not _TICKER_RE.match(ticker):
        raise HTTPException(400, "Invalid ticker symbol")
    try:
        from services.stock_data import get_stock_info
        from services.claude_analyst import ClaudeAnalyst

        info = get_stock_info(ticker)
        analyst = ClaudeAnalyst()
        result = analyst.score_watchlist_ticker(ticker, info)
        return {
            "ticker": ticker,
            "wheel_score": result.get("wheel_score"),
            "wheel_grade": result.get("wheel_grade"),
            "wheel_note": result.get("wheel_note"),
            "options_score": result.get("options_score"),
            "options_grade": result.get("options_grade"),
            "options_note": result.get("options_note"),
            "longterm_score": result.get("longterm_score"),
            "longterm_grade": result.get("longterm_grade"),
            "longterm_note": result.get("longterm_note"),
            "best_strategy": result.get("best_strategy"),
            "summary": result.get("summary"),
            "earnings_warning": result.get("earnings_warning"),
        }
    except Exception as e:
        logger.error("quick score failed for %s: %s", ticker, e)
        raise HTTPException(500, str(e))


@router.post("/{ticker}/score")
def score_ticker(ticker: str, db: Session = Depends(get_db)):
    """Run a fresh multi-strategy score for a watchlist ticker."""
    ticker = ticker.upper()
    item = db.query(WatchlistItem).filter(WatchlistItem.ticker == ticker).first()
    if not item:
        raise HTTPException(404, f"{ticker} not found in watchlist")

    try:
        from services.stock_data import get_stock_info
        from services.claude_analyst import ClaudeAnalyst

        info = get_stock_info(ticker)
        analyst = ClaudeAnalyst()
        result = analyst.score_watchlist_ticker(ticker, info)

        item.wheel_score = result.get("wheel_score")
        item.wheel_grade = result.get("wheel_grade")
        item.options_score = result.get("options_score")
        item.options_grade = result.get("options_grade")
        item.longterm_score = result.get("longterm_score")
        item.longterm_grade = result.get("longterm_grade")
        item.best_strategy = result.get("best_strategy")
        item.score_summary = result.get("summary")
        item.earnings_date = result.get("earnings_date")
        item.earnings_warning = result.get("earnings_warning")
        item.last_scored = datetime.now(timezone.utc)

        db.commit()
        db.refresh(item)
    except Exception as e:
        logger.error("watchlist score failed for %s: %s", ticker, e)
        raise HTTPException(500, str(e))

    return _serialize(item)


def _serialize(item: WatchlistItem) -> dict:
    return {
        "id": item.id,
        "ticker": item.ticker,
        "notes": item.notes,
        "added_at": item.added_at.isoformat() if item.added_at else None,
        "wheel_score": item.wheel_score,
        "wheel_grade": item.wheel_grade,
        "options_score": item.options_score,
        "options_grade": item.options_grade,
        "longterm_score": item.longterm_score,
        "longterm_grade": item.longterm_grade,
        "best_strategy": item.best_strategy,
        "score_summary": item.score_summary,
        "earnings_date": item.earnings_date,
        "earnings_warning": item.earnings_warning,
        "last_scored": item.last_scored.isoformat() if item.last_scored else None,
    }
