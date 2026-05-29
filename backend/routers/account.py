from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models.account import AccountBalance, AccountTransaction
from models.wheel import WheelPosition, WheelStatus

router = APIRouter(prefix="/api/account", tags=["Account"])

MAX_POSITION_PCT = 0.10  # never risk more than 10% on a single wheel trade


def _get_or_create(db: Session) -> AccountBalance:
    row = db.query(AccountBalance).filter(AccountBalance.id == 1).first()
    if row:
        return row
    try:
        row = AccountBalance(id=1, balance=0.0)
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    except Exception:
        db.rollback()
        row = db.query(AccountBalance).filter(AccountBalance.id == 1).first()
        if row:
            return row
        raise


def _capital_at_risk(db: Session) -> float:
    """Sum of capital committed across all non-closed wheel positions.
    put_active: collateral = strike × shares (cost_basis not yet set).
    assigned/call_active: cost_basis × shares (effective purchase price).
    """
    positions = (
        db.query(WheelPosition)
        .filter(WheelPosition.status != WheelStatus.closed)
        .all()
    )
    total = 0.0
    for p in positions:
        shares = p.shares or 100
        if p.cost_basis:
            total += p.cost_basis * shares
        elif p.put_strike:
            total += p.put_strike * shares
    return total


@router.get("")
def get_balance(db: Session = Depends(get_db)):
    row = _get_or_create(db)
    at_risk = _capital_at_risk(db)
    max_position = round(row.balance * MAX_POSITION_PCT, 2)
    return {
        "balance": round(row.balance, 2),
        "capital_at_risk": round(at_risk, 2),
        "available_capital": round(row.balance - at_risk, 2),
        "max_single_position": max_position,
        "max_position_pct": MAX_POSITION_PCT * 100,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


class DepositBody(BaseModel):
    amount: float = Field(..., description="Positive to deposit, negative to withdraw")
    note: str = Field("", max_length=300)


@router.post("/deposit")
def deposit(body: DepositBody, db: Session = Depends(get_db)):
    row = _get_or_create(db)
    row.balance = round(row.balance + body.amount, 2)
    row.updated_at = datetime.now(timezone.utc)

    txn = AccountTransaction(amount=body.amount, note=body.note or None)
    db.add(txn)
    db.commit()
    db.refresh(row)

    at_risk = _capital_at_risk(db)
    return {
        "balance": round(row.balance, 2),
        "capital_at_risk": round(at_risk, 2),
        "available_capital": round(row.balance - at_risk, 2),
        "max_single_position": round(row.balance * MAX_POSITION_PCT, 2),
        "max_position_pct": MAX_POSITION_PCT * 100,
        "updated_at": row.updated_at.isoformat(),
        "transaction": {"amount": body.amount, "note": body.note},
    }


class SetBalanceBody(BaseModel):
    balance: float = Field(..., gt=0)
    note: str = Field("Manual balance update", max_length=300)


@router.patch("")
def set_balance(body: SetBalanceBody, db: Session = Depends(get_db)):
    row = _get_or_create(db)
    diff = round(body.balance - row.balance, 2)
    row.balance = round(body.balance, 2)
    row.updated_at = datetime.now(timezone.utc)

    txn = AccountTransaction(amount=diff, note=body.note)
    db.add(txn)
    db.commit()
    db.refresh(row)

    at_risk = _capital_at_risk(db)
    return {
        "balance": round(row.balance, 2),
        "capital_at_risk": round(at_risk, 2),
        "available_capital": round(row.balance - at_risk, 2),
        "max_single_position": round(row.balance * MAX_POSITION_PCT, 2),
        "max_position_pct": MAX_POSITION_PCT * 100,
        "updated_at": row.updated_at.isoformat(),
    }


@router.get("/transactions")
def get_transactions(db: Session = Depends(get_db)):
    txns = (
        db.query(AccountTransaction)
        .order_by(AccountTransaction.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": t.id,
            "amount": t.amount,
            "note": t.note,
            "created_at": t.created_at.isoformat(),
        }
        for t in txns
    ]
