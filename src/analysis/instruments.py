"""
Instrument classification — feeds instrument-aware scoring weights.

The audit of 733 graded verdicts found GOLDBEES/SILVERBEES sitting at ~50%
directional accuracy, materially worse than the equity universe (60-90%),
consistent with being scored on the same rubric as an equity — Fundamental
and Valuation are meaningless for a commodity ETF. The live production
prompt (`agent/routine_prompt.md` STEP 2) already carries a correct,
instrument-aware weight table; this module mirrors it in code so this repo's
own pipeline stays consistent with production, and to catch a bare ticker
being scored on the wrong profile at review time rather than in prod.

Extend `INSTRUMENT_TYPES` as the universe grows; anything not listed defaults
to EQUITY.
"""
from __future__ import annotations

from enum import Enum


class InstrumentType(str, Enum):
    EQUITY = "EQUITY"
    INDEX_ETF = "INDEX_ETF"
    COMMODITY_ETF = "COMMODITY_ETF"


INSTRUMENT_TYPES: dict[str, InstrumentType] = {
    "GROWWN200": InstrumentType.INDEX_ETF,
    "GOLDBEES": InstrumentType.COMMODITY_ETF,
    "SILVERBEES": InstrumentType.COMMODITY_ETF,
}


def instrument_type(ticker: str) -> InstrumentType:
    return INSTRUMENT_TYPES.get(ticker.upper(), InstrumentType.EQUITY)
