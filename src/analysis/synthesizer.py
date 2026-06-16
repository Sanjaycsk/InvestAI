"""
The 'Intelligence' synthesis.

Takes the YouTube transcripts and RSS articles, figures out which tickers are
being discussed, gathers the evidence for each, and produces the structured
verdict you specified:  {ticker, sentiment_score, rationale, recommended_action}
as a validated `Recommendation`.

Two backends:
  * Claude  — used when ANTHROPIC_API_KEY is set. Best at nuance / Hinglish.
  * Heuristic — keyword sentiment, used when no key (so the dry-run still works).
    It's transparent and deterministic; never mistaken for real LLM analysis
    because the rationale and `source` say "heuristic".

If a Claude call fails for any reason, we fall back to the heuristic rather than
producing nothing.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from config import config
from src.analysis.schema import Action, Flag, Recommendation
from src.analysis.tickers import company_name, extract_candidates
from src.data.news_ingest import Article
from src.data.youtube_ingest import TranscriptDoc

log = logging.getLogger(__name__)

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")

_POSITIVE = {
    "bullish", "buy", "accumulate", "strong", "attractive", "undervalued",
    "growth", "positive", "conviction", "compounder", "robust", "upgrade",
    "outperform", "multibagger", "opportunity", "reassures", "constructive",
    "steady", "quality", "high", "wins",
}
_NEGATIVE = {
    "avoid", "cautious", "sell", "overvalued", "overheated", "weak", "concern",
    "concerns", "uncertain", "uncertainty", "risk", "downgrade", "expensive",
    "bearish", "slip", "slips", "pressure", "pressures", "linger", "lingers",
}


@dataclass
class Evidence:
    symbol: str
    mention_count: int = 0
    transcript_snippets: list[tuple[str, float, str]] = field(default_factory=list)  # (channel, weight, text)
    articles: list[Article] = field(default_factory=list)

    @property
    def sources(self) -> set[str]:
        s = {c for c, _, _ in self.transcript_snippets}
        s |= {a.source for a in self.articles}
        return s


# ----------------------------------------------------------- evidence
def build_evidence(
    transcripts: list[TranscriptDoc], articles: list[Article]
) -> dict[str, Evidence]:
    ev: dict[str, Evidence] = {}

    for doc in transcripts:
        for sentence in _SENT_SPLIT.split(doc.text):
            for symbol in extract_candidates(sentence):
                e = ev.setdefault(symbol, Evidence(symbol))
                e.transcript_snippets.append((doc.channel, doc.weight, sentence.strip()))
                e.mention_count += 1

    for art in articles:
        for symbol in art.tickers:
            e = ev.setdefault(symbol, Evidence(symbol))
            e.articles.append(art)
            e.mention_count += art.tickers[symbol]

    return ev


# ---------------------------------------------------------- public API
def synthesize(
    transcripts: list[TranscriptDoc], articles: list[Article]
) -> list[Recommendation]:
    evidence = build_evidence(transcripts, articles)
    evidence = {
        s: e for s, e in evidence.items()
        if e.mention_count >= config.MIN_MENTIONS_TO_SUGGEST
    }
    if not evidence:
        log.info("No tickers met the mention threshold.")
        return []

    if config.ANTHROPIC_API_KEY:
        try:
            recs = _synthesize_with_claude(evidence)
            if recs:
                return _rank(recs)
            log.warning("Claude returned nothing usable; falling back to heuristic.")
        except Exception as exc:
            log.warning("Claude synthesis failed (%s); falling back to heuristic.", exc)

    return _rank([_heuristic_one(e) for e in evidence.values()])


def _rank(recs: list[Recommendation]) -> list[Recommendation]:
    return sorted(recs, key=lambda r: r.sentiment_score, reverse=True)


# ------------------------------------------------------------ heuristic
def _score_text(text: str, weight: float) -> tuple[float, float]:
    words = re.findall(r"[a-z']+", text.lower())
    pos = sum(1 for w in words if w in _POSITIVE) * weight
    neg = sum(1 for w in words if w in _NEGATIVE) * weight
    return pos, neg


def _top_reasons(e: Evidence, want_positive: bool, k: int = 3) -> list[str]:
    """
    The actual headlines/quotes driving the verdict — the 'why'. Each candidate
    is scored by net sentiment; we surface the ones pointing the same direction
    as the overall call so the reader sees concrete catalysts, not just counts.
    """
    candidates: list[tuple[float, str]] = []
    for art in e.articles:
        p, n = _score_text(art.text, art.weight)
        candidates.append((p - n, f"{art.title.strip()} ({art.source})"))
    for channel, weight, text in e.transcript_snippets:
        p, n = _score_text(text, weight)
        snippet = text if len(text) <= 160 else text[:157] + "..."
        candidates.append((p - n, f"“{snippet}” ({channel})"))

    # Same-direction reasons first, strongest signal first.
    relevant = [(s, t) for s, t in candidates if (s > 0) == want_positive and s != 0]
    relevant.sort(key=lambda x: x[0], reverse=want_positive)
    reasons = [t for _, t in relevant[:k]]
    # Fall back to plain mentions if nothing carried explicit sentiment words.
    if not reasons:
        reasons = [t for _, t in candidates[:k]]
    return reasons


def _heuristic_one(e: Evidence) -> Recommendation:
    pos = neg = 0.0
    for _, weight, text in e.transcript_snippets:
        p, n = _score_text(text, weight)
        pos += p
        neg += n
    for art in e.articles:
        p, n = _score_text(art.text, art.weight)
        pos += p
        neg += n

    # (-1, 1); the +1 tempers conclusions drawn from very little evidence.
    score = round((pos - neg) / (pos + neg + 1.0), 3)
    flag, action = _flag_action(score)

    name = company_name(e.symbol)
    direction = (
        "Positive coverage" if score >= 0.15
        else "Negative/cautious coverage" if score <= -0.15
        else "Mixed / thin signal"
    )
    reasons = _top_reasons(e, want_positive=(score >= 0))
    why = " | ".join(reasons) if reasons else "no clear catalyst in the evidence"
    rationale = (
        f"{name} ({e.symbol}). {direction}. "
        f"Why: {why} "
        f"[{e.mention_count} mention(s) across {len(e.sources)} source(s); "
        f"tone {pos:.1f} positive vs {neg:.1f} negative]."
    )
    return Recommendation(
        ticker=e.symbol, flag=flag, sentiment_score=score,
        recommended_action=action, rationale=rationale,
        source="synthesis:heuristic",
    )


def _flag_action(score: float) -> tuple[Flag, Action]:
    if score >= 0.5:
        return Flag.GREEN, Action.BUY
    if score >= 0.15:
        return Flag.GREEN, Action.ACCUMULATE
    if score <= -0.15:
        return Flag.RED, Action.WATCH  # caution / avoid (discovery, not a holding)
    return Flag.NEUTRAL, Action.WATCH


# --------------------------------------------------------------- claude
_SYSTEM_PROMPT = (
    "You are an equity research assistant for Indian (NSE/BSE) markets. You are "
    "given evidence (YouTube commentary snippets + news headlines) about several "
    "tickers. For EACH ticker, synthesize a conservative verdict. You never state "
    "advice as fact; you summarize the weight of evidence and assign a calibrated "
    "sentiment in [-1, 1]. Prefer WATCH when signals are thin or conflicting. "
    "Return ONLY a JSON array, one object per ticker, each: "
    '{"ticker": str, "sentiment_score": float, "rationale": str (<=2 sentences), '
    '"recommended_action": one of ["BUY","ACCUMULATE","HOLD","REDUCE","SELL","WATCH"]}.'
)


def _evidence_payload(evidence: dict[str, Evidence]) -> str:
    blocks = []
    for symbol, e in evidence.items():
        yt = [f"[{c} (trust {w})] {t}" for c, w, t in e.transcript_snippets[:6]]
        news = [f"[{a.source} (trust {a.weight})] {a.title}" for a in e.articles[:6]]
        blocks.append({
            "ticker": symbol,
            "mentions": e.mention_count,
            "youtube": yt,
            "news": news,
        })
    return json.dumps(blocks, ensure_ascii=False, indent=2)


def _synthesize_with_claude(evidence: dict[str, Evidence]) -> list[Recommendation]:
    from anthropic import Anthropic

    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=2000,
        system=_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": "Evidence:\n" + _evidence_payload(evidence),
        }],
    )
    raw = "".join(block.text for block in msg.content if block.type == "text")
    data = _parse_json_array(raw)

    recs: list[Recommendation] = []
    for item in data:
        symbol = str(item.get("ticker", "")).upper()
        if symbol not in evidence:
            continue
        try:
            action = Action(str(item.get("recommended_action", "WATCH")).upper())
        except ValueError:
            action = Action.WATCH
        score = max(-1.0, min(1.0, float(item.get("sentiment_score", 0.0))))
        flag = (Flag.GREEN if score >= 0.15
                else Flag.RED if score <= -0.15 else Flag.NEUTRAL)
        recs.append(Recommendation(
            ticker=symbol, flag=flag, sentiment_score=round(score, 3),
            recommended_action=action,
            rationale=str(item.get("rationale", "")).strip(),
            source="synthesis:claude",
        ))
    return recs


def _parse_json_array(raw: str) -> list[dict]:
    """Extract the JSON array from the model's reply (tolerates stray prose/fences)."""
    raw = raw.strip()
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1:
        return []
    try:
        return json.loads(raw[start:end + 1])
    except json.JSONDecodeError:
        return []
