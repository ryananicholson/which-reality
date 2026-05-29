import enum
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey, Enum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class WheelStatus(str, enum.Enum):
    put_active = "put_active"
    assigned = "assigned"
    call_active = "call_active"
    closed = "closed"


class WheelRecommendation(Base):
    __tablename__ = "wheel_recommendations"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(10), nullable=False)
    rank = Column(Integer, nullable=False)
    score = Column(Float, nullable=False)
    grade = Column(String(2), nullable=False)
    explanation = Column(Text, nullable=False)
    put_strike = Column(Float, nullable=True)
    put_expiry = Column(String(12), nullable=True)
    put_premium = Column(Float, nullable=True)
    iv_rank = Column(Float, nullable=True)
    # Dual confidence scores
    quant_score = Column(Float, nullable=True)
    qual_score = Column(Float, nullable=True)
    combined_score = Column(Float, nullable=True)
    quant_components = Column(Text, nullable=True)
    # Entry details
    pct_otm = Column(Float, nullable=True)         # % OTM for the put strike
    breakeven = Column(Float, nullable=True)        # put_strike - put_premium
    assignment_chance_pct = Column(Float, nullable=True)   # e.g. 30 → "30% chance you own shares"
    assignment_risk = Column(String(10), nullable=True)    # LOW / MODERATE / HIGH
    run_at = Column(DateTime(timezone=True), nullable=False, index=True)
    accepted = Column(Boolean, default=False, nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=True)

    position = relationship(
        "WheelPosition", back_populates="recommendation", uselist=False
    )


class WheelPosition(Base):
    __tablename__ = "wheel_positions"

    id = Column(Integer, primary_key=True, index=True)
    recommendation_id = Column(
        Integer, ForeignKey("wheel_recommendations.id"), nullable=False
    )
    ticker = Column(String(10), nullable=False)
    status = Column(
        Enum(WheelStatus), default=WheelStatus.put_active, nullable=False, index=True
    )

    # Put leg
    put_strike = Column(Float, nullable=False)
    put_expiry = Column(String(12), nullable=False)
    put_premium_rcvd = Column(Float, nullable=True)
    put_opened_at = Column(DateTime(timezone=True), server_default=func.now())

    # Assignment
    assigned_at = Column(DateTime(timezone=True), nullable=True)
    cost_basis = Column(Float, nullable=True)
    shares = Column(Integer, default=100)

    # Covered call leg
    call_strike = Column(Float, nullable=True)
    call_expiry = Column(String(12), nullable=True)
    call_premium_rcvd = Column(Float, nullable=True)
    call_opened_at = Column(DateTime(timezone=True), nullable=True)
    call_suggestion = Column(Text, nullable=True)
    call_suggestion_at = Column(DateTime(timezone=True), nullable=True)

    # Closure
    closed_at = Column(DateTime(timezone=True), nullable=True)
    total_pnl = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)

    recommendation = relationship("WheelRecommendation", back_populates="position")
    history = relationship("WheelHistory", back_populates="position", order_by="WheelHistory.changed_at")


class WheelHistory(Base):
    __tablename__ = "wheel_history"

    id = Column(Integer, primary_key=True)
    position_id = Column(Integer, ForeignKey("wheel_positions.id"), nullable=False)
    from_status = Column(Enum(WheelStatus), nullable=True)
    to_status = Column(Enum(WheelStatus), nullable=False)
    note = Column(Text, nullable=True)
    changed_at = Column(DateTime(timezone=True), server_default=func.now())

    position = relationship("WheelPosition", back_populates="history")
