from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Float, String, DateTime
from database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class WatchlistItem(Base):
    __tablename__ = "watchlist"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(10), unique=True, nullable=False)
    notes = Column(String(500), nullable=True)
    added_at = Column(DateTime, default=_utcnow)

    # Cached multi-strategy scores (refreshed on demand)
    wheel_score = Column(Float, nullable=True)
    wheel_grade = Column(String(2), nullable=True)
    options_score = Column(Float, nullable=True)
    options_grade = Column(String(2), nullable=True)
    longterm_score = Column(Float, nullable=True)
    longterm_grade = Column(String(2), nullable=True)
    best_strategy = Column(String(30), nullable=True)
    score_summary = Column(String(1000), nullable=True)
    earnings_date = Column(String(20), nullable=True)
    earnings_warning = Column(String(200), nullable=True)
    last_scored = Column(DateTime, nullable=True)
