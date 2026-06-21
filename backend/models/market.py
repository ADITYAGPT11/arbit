"""Market data Pydantic models."""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class WatchlistItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    symbol: str
    exchange: str  # NSE or BSE
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ArbitrageOpportunity(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str
    symbol: str
    nse_price: Optional[float] = None
    bse_price: Optional[float] = None
    futures_price: Optional[float] = None
    spot_price: Optional[float] = None
    spread_pct: float
    net_profit: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BacktestRequest(BaseModel):
    strategy: str
    symbol: str
    start_date: str
    end_date: str
    initial_capital: float = 1000000
