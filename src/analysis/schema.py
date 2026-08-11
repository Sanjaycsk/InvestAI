"""
The contract between every layer.

The analysis layer produces `Recommendation` objects. The store persists them.
The notifier renders them into Telegram messages with approval buttons. The
execution layer consumes an *approved* one. No layer imports another's logic —
they only agree on this schema. That is what keeps the system modular.
"""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Action(str, Enum):
    """What the system suggests. The human always has final say."""
    BUY = "BUY"
    ACCUMULATE = "ACCUMULATE"
    HOLD = "HOLD"
    REDUCE = "REDUCE"
    SELL = "SELL"
    WATCH = "WATCH"


class Flag(str, Enum):
    RED = "RED"        # sell / withdraw / trend weakening
    GREEN = "GREEN"    # buy / accumulate
    NEUTRAL = "NEUTRAL"


class RecStatus(str, Enum):
    PENDING = "PENDING"        # awaiting your decision
    APPROVED = "APPROVED"      # you approved; queued/executed
    REJECTED = "REJECTED"      # you declined
    EXPIRED = "EXPIRED"        # approval window passed
    SIMULATED = "SIMULATED"    # executed in DUMMY_MODE
    EXECUTED = "EXECUTED"      # real order placed
    FAILED = "FAILED"          # execution attempted but errored


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Recommendation(BaseModel):
    """One actionable idea about one ticker."""

    recommendation_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    ticker: str
    exchange: str = "NSE"

    flag: Flag = Flag.NEUTRAL
    # -1.0 (strong sell/avoid) .. +1.0 (strong buy/accumulate)
    sentiment_score: float = Field(0.0, ge=-1.0, le=1.0)
    rationale: str = ""
    recommended_action: Action = Action.WATCH

    # Trade hint (the human re-validates before approving).
    suggested_qty: int = 0
    price_at_analysis: Optional[float] = None

    # Risk management. Independent of any trend/SMA signal — the audit found
    # the 200-DMA cross was the *only* exit trigger in the system, which is
    # far too lagging to cap a single trade's downside. A BUY/ACCUMULATE idea
    # gets a stop set at analysis time; nothing waits for a moving average to
    # notice the position already lost more than the risk budget allows.
    stop_loss_price: Optional[float] = None
    # 0..1 calibrated probability of the call being directionally correct,
    # from src.analysis.calibration — separate from the raw sentiment_score,
    # which the audit showed is NOT well calibrated to actual outcomes
    # (highest-conviction "Strong Buy" bucket had the worst hit rate).
    calibrated_confidence: Optional[float] = None

    # Provenance, e.g. "technical:200dma", "youtube:<channel>", "news:brightdata".
    source: str = "system"

    # Approval security: a stale or forged button cannot trigger a trade.
    approval_token: str = Field(default_factory=lambda: secrets.token_urlsafe(16))
    status: RecStatus = RecStatus.PENDING
    created_at: datetime = Field(default_factory=_utcnow)
    expires_at: Optional[datetime] = None

    def with_ttl(self, minutes: int) -> "Recommendation":
        """Set the approval expiry relative to creation time."""
        self.expires_at = self.created_at + timedelta(minutes=minutes)
        return self

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        if self.expires_at is None:
            return False
        return (now or _utcnow()) > self.expires_at

    @property
    def notional(self) -> Optional[float]:
        if self.price_at_analysis is None:
            return None
        return round(self.price_at_analysis * self.suggested_qty, 2)
