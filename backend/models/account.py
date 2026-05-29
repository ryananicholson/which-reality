from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Float, String, DateTime
from database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class AccountBalance(Base):
    __tablename__ = "account_balance"

    id = Column(Integer, primary_key=True, default=1)
    balance = Column(Float, nullable=False, default=0.0)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class AccountTransaction(Base):
    __tablename__ = "account_transactions"

    id = Column(Integer, primary_key=True, index=True)
    amount = Column(Float, nullable=False)
    note = Column(String(300), nullable=True)
    created_at = Column(DateTime, default=_utcnow)
