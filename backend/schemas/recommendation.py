from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class RecommendationSchema(BaseModel):
    id: int
    tab: str
    ticker: str
    rank: int
    score: float
    grade: str
    explanation: str
    # Dual confidence scores
    quant_score: Optional[float] = None
    qual_score: Optional[float] = None
    combined_score: Optional[float] = None
    quant_components: Optional[str] = None
    # Options-specific
    option_type: Optional[str] = None
    strategy_type: Optional[str] = None
    strike: Optional[float] = None
    expiry: Optional[str] = None
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    stop_loss: Optional[float] = None
    # Multi-leg strikes
    short_call_strike: Optional[float] = None
    long_call_strike: Optional[float] = None
    short_put_strike: Optional[float] = None
    long_put_strike: Optional[float] = None
    net_credit: Optional[float] = None
    max_profit: Optional[float] = None
    max_loss: Optional[float] = None
    breakeven_low: Optional[float] = None
    breakeven_high: Optional[float] = None
    underlying_entry: Optional[float] = None
    underlying_target: Optional[float] = None
    underlying_stop: Optional[float] = None
    # Long-term-specific
    investment_type: Optional[str] = None
    target_price: Optional[float] = None
    time_horizon: Optional[str] = None
    buy_zone_low: Optional[float] = None
    buy_zone_high: Optional[float] = None
    invalidation_stop: Optional[float] = None
    run_at: datetime

    model_config = {"from_attributes": True}
