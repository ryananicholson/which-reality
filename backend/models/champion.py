from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Float, String, DateTime
from database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class Champion(Base):
    __tablename__ = "champions"

    id = Column(Integer, primary_key=True, index=True)
    strategy = Column(String(20), nullable=False)
    ticker = Column(String(10), nullable=False)
    score = Column(Float, nullable=True)
    grade = Column(String(2), nullable=True)
    reason = Column(String(1000), nullable=True)
    universe_size = Column(Integer, nullable=True)
    survivors_count = Column(Integer, nullable=True)
    run_at = Column(DateTime, default=_utcnow)
