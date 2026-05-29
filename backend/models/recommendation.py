import enum
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Enum
from sqlalchemy.sql import func
from database import Base


class TabType(str, enum.Enum):
    options = "options"
    longterm = "longterm"


class GradeEnum(str, enum.Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, index=True)
    tab = Column(Enum(TabType), nullable=False, index=True)
    ticker = Column(String(10), nullable=False)
    rank = Column(Integer, nullable=False)
    score = Column(Float, nullable=False)
    grade = Column(Enum(GradeEnum), nullable=False)
    explanation = Column(Text, nullable=False)

    # Dual confidence scores
    quant_score = Column(Float, nullable=True)     # math-based 0-100
    qual_score = Column(Float, nullable=True)      # Claude qualitative 0-100
    combined_score = Column(Float, nullable=True)  # 40% quant + 60% qual

    # Quant score components (JSON string)
    quant_components = Column(Text, nullable=True)

    # Options-specific
    option_type = Column(String(4), nullable=True)   # CALL | PUT | N/A (multi-leg)
    strategy_type = Column(String(20), nullable=True)  # single_leg | iron_condor | bull_put_spread | bear_call_spread | bull_call_spread | bear_put_spread
    strike = Column(Float, nullable=True)
    expiry = Column(String(12), nullable=True)
    entry_price = Column(Float, nullable=True)    # premium paid/received
    exit_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    # Multi-leg strikes
    short_call_strike = Column(Float, nullable=True)
    long_call_strike = Column(Float, nullable=True)
    short_put_strike = Column(Float, nullable=True)
    long_put_strike = Column(Float, nullable=True)
    # Payoff
    net_credit = Column(Float, nullable=True)     # net credit (positive) or debit (negative)
    max_profit = Column(Float, nullable=True)
    max_loss = Column(Float, nullable=True)
    breakeven_low = Column(Float, nullable=True)
    breakeven_high = Column(Float, nullable=True)
    # ATR-based underlying price targets (options)
    underlying_entry = Column(Float, nullable=True)
    underlying_target = Column(Float, nullable=True)
    underlying_stop = Column(Float, nullable=True)

    # Long-term-specific
    investment_type = Column(String(10), nullable=True)  # growth | income
    target_price = Column(Float, nullable=True)
    time_horizon = Column(String(30), nullable=True)
    # Long-term entry zone
    buy_zone_low = Column(Float, nullable=True)
    buy_zone_high = Column(Float, nullable=True)
    invalidation_stop = Column(Float, nullable=True)

    run_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
