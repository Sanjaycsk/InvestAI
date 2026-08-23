"""Unit tests for the 200-DMA flag logic. Run: pytest -q"""
from __future__ import annotations

import pathlib
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src.analysis.schema import Action, Flag  # noqa: E402
from src.analysis.technical import assess_trend, simple_moving_average  # noqa: E402


def _series(values):
    idx = pd.bdate_range(end="2026-06-15", periods=len(values))
    return pd.Series(values, index=idx, name="close")


def test_sma_returns_none_when_insufficient_history():
    assert simple_moving_average(_series([1, 2, 3]), window=200) is None


def test_red_flag_when_close_below_sma():
    # A long downtrend -> last close well below the 200-DMA.
    falling = _series(list(range(400, 0, -1)))  # 400 -> 1
    rec = assess_trend("TESTDOWN", falling, held_qty=40)
    assert rec.flag is Flag.RED
    assert rec.recommended_action is Action.REDUCE
    assert rec.suggested_qty == 10  # quarter of 40


def test_green_flag_when_close_above_sma():
    rising = _series(list(range(1, 401)))
    rec = assess_trend("TESTUP", rising, held_qty=10)
    assert rec.flag is Flag.GREEN
    assert rec.recommended_action is Action.HOLD


def test_buffer_zone_close_is_not_described_as_above_the_sma(monkeypatch):
    # With a non-zero buffer a close just BELOW the SMA stays GREEN (the trend
    # isn't flagged as weakening yet) — but it must not be reported as being
    # "ABOVE" the SMA, which is what the old single-branch wording did.
    from config import config
    from src.analysis import technical

    monkeypatch.setattr(config, "SMA_RED_FLAG_BUFFER", 0.02)  # 2% dead zone

    # Flat at 100, with the final close nudged to 99 — about 1% under the SMA,
    # i.e. inside the 2% dead zone.
    flat_then_dip = [100.0] * 399 + [99.0]
    rec = technical.assess_trend("TESTBUFFER", _series(flat_then_dip))

    assert rec.flag is Flag.GREEN
    assert "ABOVE" not in rec.rationale
    assert "below" in rec.rationale


def test_sentiment_score_within_bounds():
    rising = _series(list(range(1, 401)))
    rec = assess_trend("TESTUP", rising)
    assert -1.0 <= rec.sentiment_score <= 1.0
