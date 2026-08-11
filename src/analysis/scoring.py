"""
Composite scoring — the weighted roll-up of sub-scores into one 0-100 number
and a Buy/Hold/Sell category, matching the rubric already in production (see
`agent/routine_prompt.md` STEP 2 / `AGENT.md` "Scoring framework"):
  - Equities:        Fundamental 30 / Technical 20 / Valuation 20 / Macro 15 / Sentiment 5 / Risk 10
  - Index ETF:        Macro 40 / Technical 35 / Valuation 15 / Sentiment 10 (no Fundamental)
  - Commodity ETFs:   Technical 35 / Macro 30 / Sentiment 25 / Risk 10 (no Fundamental/Valuation)
The live prompt already gets this right — this module exists so the LOCAL
pipeline (this repo) can compute the same composite in code once it grows
fundamental/valuation/macro sources of its own, with two fixes the audit
showed the *scoring logic itself* needs regardless of where it runs:

1. Instrument-aware weights (see `instruments.py`) — an ETF has no
   Fundamental/Valuation score worth a combined 50% of the composite, so that
   weight is redistributed to Technical/Macro/Sentiment/Risk instead of
   silently defaulting to a meaningless number.
2. Missing sub-scores are renormalized over, not treated as zero — a
   temporarily-unavailable component should not drag the composite down as if
   it were bearish evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.analysis.instruments import InstrumentType, instrument_type

# component -> weight, per instrument type. Must each sum to 1.0.
# Mirrors agent/routine_prompt.md STEP 2 exactly — keep these in sync.
SCORE_WEIGHTS: dict[InstrumentType, dict[str, float]] = {
    InstrumentType.EQUITY: {
        "fundamental": 0.30,
        "technical": 0.20,
        "valuation": 0.20,
        "macro": 0.15,
        "sentiment": 0.05,
        "risk": 0.10,
    },
    InstrumentType.INDEX_ETF: {
        "fundamental": 0.00,
        "technical": 0.35,
        "valuation": 0.15,
        "macro": 0.40,
        "sentiment": 0.10,
        "risk": 0.00,
    },
    InstrumentType.COMMODITY_ETF: {
        "fundamental": 0.00,
        "technical": 0.35,
        "valuation": 0.00,
        "macro": 0.30,
        "sentiment": 0.25,
        "risk": 0.10,
    },
}

CATEGORY_BANDS: list[tuple[float, str]] = [
    (80.0, "Strong Buy"),
    (70.0, "Buy on Dip"),
    (60.0, "Watchlist"),
    (45.0, "Hold"),
    (0.0, "Avoid/Sell"),
]


@dataclass
class ScoreInputs:
    fundamental: Optional[float] = None
    technical: Optional[float] = None
    valuation: Optional[float] = None
    macro: Optional[float] = None
    sentiment: Optional[float] = None
    risk: Optional[float] = None

    def as_dict(self) -> dict[str, Optional[float]]:
        return {
            "fundamental": self.fundamental, "technical": self.technical,
            "valuation": self.valuation, "macro": self.macro,
            "sentiment": self.sentiment, "risk": self.risk,
        }


def composite_score(ticker: str, inputs: ScoreInputs) -> float:
    """
    Weighted 0-100 composite for `ticker`, using the weight profile for its
    instrument type. Components that are None are excluded and the remaining
    weights are renormalized to still sum to 1.0, so a missing input dilutes
    confidence rather than counting as a bearish zero.
    """
    weights = SCORE_WEIGHTS[instrument_type(ticker)]
    present = {k: v for k, v in inputs.as_dict().items() if v is not None and weights.get(k, 0) > 0}
    if not present:
        raise ValueError(f"no scoreable inputs for {ticker} given its instrument type")
    total_weight = sum(weights[k] for k in present)
    return round(sum(v * weights[k] for k, v in present.items()) / total_weight, 2)


def categorize(score: float) -> str:
    for floor, label in CATEGORY_BANDS:
        if score >= floor:
            return label
    return "Avoid/Sell"
