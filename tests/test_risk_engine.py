"""
Tests for the Phase 2 risk/scoring engine: verified pricing, instrument-aware
composite scoring, empirical calibration, conviction-scaled position sizing,
the earnings-day guard, and the stop-loss circuit breaker. Run: pytest -q
"""
from __future__ import annotations

import pathlib
import sys
from datetime import date

import pandas as pd
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from config import config  # noqa: E402
from src.analysis.calibration import calibrated_confidence  # noqa: E402
from src.analysis.earnings_calendar import is_results_window  # noqa: E402
from src.analysis.instruments import InstrumentType, instrument_type  # noqa: E402
from src.analysis.position_sizing import position_size, stop_loss_price  # noqa: E402
from src.analysis.scoring import ScoreInputs, categorize, composite_score  # noqa: E402
from src.analysis.schema import Action, RecStatus, Recommendation  # noqa: E402
from src.data import price_data  # noqa: E402
from src.execution import order_manager  # noqa: E402
from src.store import db  # noqa: E402


# --------------------------------------------------------- verified price
class _FakeKite:
    def __init__(self, ltp: float | None):
        self._ltp = ltp

    def get_ltp(self, symbol, exchange="NSE"):
        return self._ltp


def _fresh_series(price: float) -> pd.Series:
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=5)
    return pd.Series([price] * 5, index=idx, name="close")


def test_verified_price_agrees_across_two_sources(monkeypatch):
    monkeypatch.setattr(price_data, "get_close_history", lambda *a, **k: _fresh_series(100.0))
    result = price_data.get_verified_price("TEST", kite=_FakeKite(101.0))
    assert result.is_verified
    assert result.price == pytest.approx(101.0)


def test_verified_price_rejects_disagreement(monkeypatch):
    # This is the exact shape of the real WAAREEENER bug: one source wildly
    # off from the other (357 quoted vs ~2732 actual).
    monkeypatch.setattr(price_data, "get_close_history", lambda *a, **k: _fresh_series(357.0))
    result = price_data.get_verified_price("WAAREEENER", kite=_FakeKite(2732.0))
    assert not result.is_verified
    assert "disagree" in result.warning


def test_verified_price_rejects_stale_single_source(monkeypatch):
    stale_idx = pd.bdate_range(end=pd.Timestamp.today().normalize() - pd.Timedelta(days=10), periods=5)
    stale_series = pd.Series([100.0] * 5, index=stale_idx, name="close")
    monkeypatch.setattr(price_data, "get_close_history", lambda *a, **k: stale_series)
    result = price_data.get_verified_price("TEST", kite=None)
    assert not result.is_verified
    assert "stale" in result.warning or "old" in result.warning


def test_verified_price_no_source_available(monkeypatch):
    monkeypatch.setattr(price_data, "get_close_history", lambda *a, **k: None)
    result = price_data.get_verified_price("GHOST", kite=None)
    assert not result.is_verified
    assert result.price is None


# --------------------------------------------------------------- scoring
def test_equity_uses_full_weight_profile():
    score = composite_score("RELIANCE", ScoreInputs(
        fundamental=80, technical=80, valuation=80, macro=80, sentiment=80, risk=80,
    ))
    assert score == pytest.approx(80.0)


def test_etf_ignores_fundamental_and_valuation():
    assert instrument_type("GOLDBEES") is InstrumentType.COMMODITY_ETF
    # Fundamental/valuation are garbage-in for a commodity ETF; a score there
    # must not move the composite at all once technical/macro/sentiment/risk
    # are supplied (matches agent/routine_prompt.md STEP 2's weight table).
    without_fund_val = composite_score("GOLDBEES", ScoreInputs(technical=70, macro=70, sentiment=70, risk=70))
    with_bad_fund_val = composite_score("GOLDBEES", ScoreInputs(
        fundamental=0, valuation=0, technical=70, macro=70, sentiment=70, risk=70,
    ))
    assert without_fund_val == with_bad_fund_val == pytest.approx(70.0)


def test_missing_component_renormalizes_not_zeros():
    # Only sentiment supplied -> composite should equal that value, not be
    # dragged toward zero by the other (absent) components.
    score = composite_score("RELIANCE", ScoreInputs(sentiment=62))
    assert score == pytest.approx(62.0)


def test_categorize_matches_production_bands():
    assert categorize(85) == "Strong Buy"
    assert categorize(75) == "Buy on Dip"
    assert categorize(65) == "Watchlist"
    assert categorize(50) == "Hold"
    assert categorize(30) == "Avoid/Sell"


# ------------------------------------------------------------ calibration
def test_calibration_flags_strong_buy_as_unreliable():
    # The real finding: the >80 band had n=5 and a 20% hit rate. Position
    # sizing must not treat a raw high score as automatically high-confidence.
    confidence, is_reliable, note = calibrated_confidence(85)
    assert confidence < 0.5
    assert not is_reliable


def test_calibration_trusts_the_watchlist_band():
    confidence, is_reliable, _ = calibrated_confidence(65)
    assert confidence > 0.7
    assert is_reliable


def test_calibration_bands_are_half_open_at_the_edges():
    # 60 is the boundary between the Hold (45-60) and Watchlist (60-70)
    # buckets. Half-open matching puts it in exactly one — Watchlist — rather
    # than whichever happened to be listed first in the JSON.
    edge, _, _ = calibrated_confidence(60)
    watchlist, _, _ = calibrated_confidence(65)
    hold, _, _ = calibrated_confidence(50)
    assert edge == watchlist
    assert edge != hold


def test_calibration_still_matches_a_perfect_score():
    # The top band keeps an inclusive upper edge, so 100 must not fall
    # through to the neutral fallback.
    confidence, _, note = calibrated_confidence(100)
    assert "outside any calibrated band" not in note
    assert confidence < 0.5  # the >80 band's real (terrible) hit rate


# -------------------------------------------------------- position sizing
def test_no_edge_means_no_trade():
    qty, confidence = position_size(price=1000.0, composite_score=85)  # Strong Buy band, 20% hit rate
    assert qty == 0
    assert confidence < 0.5


def test_reliable_edge_produces_a_sized_position():
    qty, confidence = position_size(price=1000.0, composite_score=65)  # Watchlist band, 78% hit rate
    assert qty > 0
    assert confidence > 0.7


def test_stop_loss_price_below_entry():
    assert stop_loss_price(1000.0, stop_loss_pct=5.0) == pytest.approx(950.0)


# ------------------------------------------------------------- earnings
def test_results_window_flags_event_day():
    assert is_results_window("SUZLON", date(2026, 7, 28))
    assert is_results_window("SUZLON", date(2026, 7, 29))  # within 1-day window
    assert not is_results_window("SUZLON", date(2026, 8, 5))


def test_results_window_ignores_unlisted_ticker():
    assert not is_results_window("RELIANCE", date(2026, 7, 28))


# --------------------------------------------------- stop-loss / breaker
def test_check_stop_loss_triggers_below_stop():
    rec = Recommendation(
        ticker="TEST", recommended_action=Action.BUY,
        price_at_analysis=100.0, stop_loss_price=95.0,
    )
    assert order_manager.check_stop_loss(rec, 94.0)
    assert not order_manager.check_stop_loss(rec, 96.0)


def test_execute_refuses_a_recommendation_that_was_never_approved(monkeypatch, tmp_path):
    # The execution layer must not take the caller's word for it: an idea
    # sitting at PENDING (or one whose in-memory copy claims APPROVED while
    # the store disagrees) must never reach the broker.
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "approval_state.db"))
    db.init_db()

    rec = Recommendation(
        ticker="TEST", recommended_action=Action.BUY,
        suggested_qty=1, price_at_analysis=100.0,
    )
    db.save_recommendation(rec)  # stored as PENDING

    rec.status = RecStatus.APPROVED  # forged in-memory approval
    result = order_manager.execute_recommendation(rec, kite=_FakeKite(100.0))

    assert not result.ok
    assert result.status is RecStatus.REJECTED
    assert "not APPROVED" in result.message


def test_execute_simulates_once_genuinely_approved(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "approval_state.db"))
    db.init_db()

    rec = Recommendation(
        ticker="TEST", recommended_action=Action.BUY,
        suggested_qty=1, price_at_analysis=100.0,
    )
    db.save_recommendation(rec)
    db.update_status(rec.recommendation_id, RecStatus.APPROVED, "approved by user")

    result = order_manager.execute_recommendation(rec, kite=_FakeKite(100.0))

    # DUMMY_MODE defaults to True, so this must simulate — never place an order.
    assert result.ok
    assert result.simulated
    assert result.status is RecStatus.SIMULATED


def test_circuit_breaker_blocks_new_buys(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "test_state.db"))
    monkeypatch.setattr(config, "MAX_DAILY_STOP_LOSSES", 1)
    db.init_db()

    rec = Recommendation(
        ticker="TEST", recommended_action=Action.BUY,
        suggested_qty=10, price_at_analysis=100.0, stop_loss_price=95.0,
    )
    order_manager.record_stop_loss(rec, 94.0)

    ok, reason = order_manager._guardrails_ok(rec, 100.0)
    assert not ok
    assert "circuit breaker" in reason
