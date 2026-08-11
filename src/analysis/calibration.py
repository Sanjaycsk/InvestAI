"""
Empirical score calibration — the 'how much ML do we actually need' answer.

The audit's biggest finding: the raw Composite Score is NOT monotonically
predictive. The highest-conviction "Strong Buy" band (>80) had the WORST
historical hit rate (20%) and a negative average move, while the mid
"Watchlist" band (60-70) was both the most accurate (78%) and the highest
volume. Sizing positions off the raw score — the obvious next step once you
have a score at all — would therefore have made things worse, not better: it
would put the most money behind the least reliable band.

733 labeled rows across 45 days is not enough to safely fit a real predictive
model (a neural net or gradient-boosted model would overfit hard and produce
false confidence — worse than the problem it's meant to solve). What that
data volume *does* support is exactly what this module does: bucket the score
and look up the band's own empirically observed hit rate. That's the model.
It gets better automatically as more graded rows accumulate — call
`refit_from_records()` periodically (e.g. monthly) once the upstream data
bugs (stale ref prices, ETF miscalibration) are fixed, since fitting on dirty
data just calibrates to the dirt.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from config import config

log = logging.getLogger(__name__)

# Below this sample size a bucket's empirical hit rate is noise, not signal —
# callers should not scale conviction/position size up on it.
MIN_RELIABLE_N = 30

# Neutral confidence used when no calibration data covers a score at all.
_FALLBACK_CONFIDENCE = 0.5


@dataclass
class CalibrationBucket:
    score_min: float
    score_max: float
    n: int
    correct: int
    wrong: int
    empirical_hit_rate: float
    avg_actual_move_pct: float
    note: str = ""

    @property
    def is_reliable(self) -> bool:
        return self.n >= MIN_RELIABLE_N


def load_calibration() -> list[CalibrationBucket]:
    try:
        with open(config.SCORE_CALIBRATION_PATH, "r", encoding="utf-8") as fh:
            raw = json.load(fh).get("buckets", [])
    except FileNotFoundError:
        log.warning("score_calibration.json not found at %s; using neutral fallback.",
                    config.SCORE_CALIBRATION_PATH)
        return []
    return [CalibrationBucket(**b) for b in raw]


def calibrated_confidence(score: float) -> tuple[float, bool, str]:
    """
    (confidence, is_reliable, note) for a raw composite `score`.

    `confidence` is the bucket's empirically observed hit rate — use this,
    not the raw score, to scale conviction. `is_reliable` is False for
    thin/noisy buckets (n < MIN_RELIABLE_N); callers should cap position size
    when it's False regardless of how high the confidence number looks.
    """
    for bucket in load_calibration():
        if bucket.score_min <= score <= bucket.score_max:
            return bucket.empirical_hit_rate, bucket.is_reliable, bucket.note
    return _FALLBACK_CONFIDENCE, False, "score outside any calibrated band"


def refit_from_records(
    records: list[tuple[float, bool]],
    bucket_edges: list[float] = (0, 45, 60, 70, 80, 100),
) -> list[dict]:
    """
    Recompute calibration buckets from fresh (composite_score, was_correct)
    pairs — e.g. a fresh export of graded Recommendation rows once the ref-
    price and ETF-weighting bugs are fixed and a clean sample has built up.
    Returns the bucket list ready to write into score_calibration.json; this
    function does not write the file itself so a human reviews the refit
    before it goes live (small-n bands especially should be sanity-checked,
    not auto-deployed).
    """
    edges = sorted(bucket_edges)
    buckets: list[dict] = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        in_band = [r for r in records if lo <= r[0] <= hi]
        n = len(in_band)
        correct = sum(1 for _, ok in in_band if ok)
        buckets.append({
            "score_min": lo, "score_max": hi, "n": n, "correct": correct,
            "wrong": n - correct,
            "empirical_hit_rate": round(correct / n, 3) if n else None,
            "avg_actual_move_pct": None,
            "note": "refit — n<{} is unreliable".format(MIN_RELIABLE_N) if n < MIN_RELIABLE_N else "",
        })
    return buckets
