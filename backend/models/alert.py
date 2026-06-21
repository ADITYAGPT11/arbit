"""Alert Pydantic model."""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class Alert(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    alert_type: str  # arbitrage, spread, price
    symbol: Optional[str] = None
    threshold: float
    telegram_chat_id: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
