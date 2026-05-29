from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models.wheel import WheelPosition, WheelStatus

router = APIRouter(prefix="/api/performance", tags=["Performance"])


@router.get("/summary")
def get_summary(db: Session = Depends(get_db)):
    positions = db.query(WheelPosition).all()

    closed = [p for p in positions if p.status == WheelStatus.closed and p.total_pnl is not None]
    active = [p for p in positions if p.status != WheelStatus.closed]

    total_trades = len(closed)
    wins = [p for p in closed if p.total_pnl > 0]
    losses = [p for p in closed if p.total_pnl <= 0]

    total_pnl = round(sum(p.total_pnl for p in closed), 2)
    avg_pnl = round(total_pnl / total_trades, 2) if total_trades else 0
    win_rate = round(len(wins) / total_trades * 100, 1) if total_trades else 0

    # Annualized return on closed positions (approximate)
    avg_return_pct = None
    returnable = [
        p for p in closed
        if p.cost_basis and p.cost_basis > 0 and p.total_pnl is not None
    ]
    if returnable:
        returns = [p.total_pnl / (p.cost_basis * (p.shares or 100)) * 100 for p in returnable]
        avg_return_pct = round(sum(returns) / len(returns), 2)

    # Active positions summary
    active_summary = [
        {
            "id": p.id,
            "ticker": p.ticker,
            "status": p.status,
            "put_strike": p.put_strike,
            "put_expiry": p.put_expiry,
            "put_premium_rcvd": p.put_premium_rcvd,
            "cost_basis": p.cost_basis,
            "shares": p.shares or 100,
            "capital_at_risk": round((p.cost_basis or 0) * (p.shares or 100), 2) if p.cost_basis else None,
            "call_strike": p.call_strike,
            "call_expiry": p.call_expiry,
            "call_premium_rcvd": p.call_premium_rcvd,
            "put_opened_at": p.put_opened_at.isoformat() if p.put_opened_at else None,
        }
        for p in active
    ]

    # Closed positions detail
    closed_detail = [
        {
            "id": p.id,
            "ticker": p.ticker,
            "total_pnl": round(p.total_pnl, 2),
            "cost_basis": p.cost_basis,
            "shares": p.shares or 100,
            "return_pct": round(p.total_pnl / (p.cost_basis * (p.shares or 100)) * 100, 2)
                if p.cost_basis and p.cost_basis > 0 else None,
            "put_opened_at": p.put_opened_at.isoformat() if p.put_opened_at else None,
            "closed_at": p.closed_at.isoformat() if p.closed_at else None,
            "notes": p.notes,
        }
        for p in closed
    ]

    return {
        "summary": {
            "total_closed_trades": total_trades,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate_pct": win_rate,
            "total_pnl": total_pnl,
            "avg_pnl_per_trade": avg_pnl,
            "avg_return_pct": avg_return_pct,
            "active_positions": len(active),
        },
        "active_positions": active_summary,
        "closed_positions": closed_detail,
    }
