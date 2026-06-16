"""Tests for ticker extraction + heuristic synthesis. Run: pytest -q"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src.analysis.schema import Flag  # noqa: E402
from src.analysis.synthesizer import build_evidence, synthesize  # noqa: E402
from src.analysis.tickers import extract_candidates  # noqa: E402
from src.data.news_ingest import SAMPLE_ARTICLES, _tag  # noqa: E402
from src.data.youtube_ingest import SAMPLE_TRANSCRIPTS  # noqa: E402


def test_extract_candidates_finds_aliases():
    counts = extract_candidates("I like Reliance Industries and HDFC Bank a lot.")
    assert "RELIANCE" in counts
    assert "HDFCBANK" in counts
    assert "ITC" not in counts  # must not match inside other words


def test_build_evidence_collects_mentions():
    articles = [_tag(a) for a in SAMPLE_ARTICLES]
    ev = build_evidence(SAMPLE_TRANSCRIPTS, articles)
    assert "RELIANCE" in ev
    assert ev["RELIANCE"].mention_count >= 1
    assert ev["RELIANCE"].sources  # at least one channel/source attributed


def test_heuristic_synthesis_directionally_correct():
    # No ANTHROPIC_API_KEY in the test env -> heuristic path.
    articles = [_tag(a) for a in SAMPLE_ARTICLES]
    recs = synthesize(SAMPLE_TRANSCRIPTS, articles)
    by_ticker = {r.ticker: r for r in recs}

    assert by_ticker["RELIANCE"].flag is Flag.GREEN
    assert by_ticker["RELIANCE"].sentiment_score > 0
    assert by_ticker["PAYTM"].flag is Flag.RED
    assert by_ticker["PAYTM"].sentiment_score < 0
    # Output is ranked best-first.
    scores = [r.sentiment_score for r in recs]
    assert scores == sorted(scores, reverse=True)
    assert recs[0].source.startswith("synthesis:")
