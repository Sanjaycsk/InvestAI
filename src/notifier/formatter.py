"""
Turns Recommendation lists into the daily Telegram message.

Three sections, matching your spec:
  1. Portfolio Health (what's doing well / poorly)
  2. Top 3 'Must Invest' candidates (Phase 2 discovery; empty until then)
  3. Safety banner so you always know whether execution is armed.
"""
from __future__ import annotations

from typing import Iterable

from config import config
from src.analysis.schema import Action, Flag, Recommendation


def _line(rec: Recommendation) -> str:
    icon = {Flag.RED: "🔴", Flag.GREEN: "🟢", Flag.NEUTRAL: "⚪"}[rec.flag]
    price = f"₹{rec.price_at_analysis:,.2f}" if rec.price_at_analysis else "n/a"
    return f"{icon} <b>{rec.ticker}</b> ({price}) — {rec.recommended_action.value}\n    {rec.rationale}"


def format_daily_summary(
    portfolio: Iterable[Recommendation],
    discovery: Iterable[Recommendation] | None = None,
) -> str:
    portfolio = list(portfolio)
    discovery = list(discovery or [])

    red = [r for r in portfolio if r.flag is Flag.RED]
    green = [r for r in portfolio if r.flag is Flag.GREEN]
    other = [r for r in portfolio if r.flag is Flag.NEUTRAL]

    parts: list[str] = ["📊 <b>Daily Portfolio &amp; Research Brief</b>", ""]

    parts.append("<b>1) Portfolio Health</b>")
    if red:
        parts.append(f"\n⚠️ <u>Needs attention ({len(red)})</u>")
        parts += [_line(r) for r in red]
    if green:
        parts.append(f"\n✅ <u>Doing well ({len(green)})</u>")
        parts += [_line(r) for r in green]
    if other:
        parts.append(f"\nℹ️ <u>No clear signal ({len(other)})</u>")
        parts += [_line(r) for r in other]
    if not portfolio:
        parts.append("No holdings found.")

    parts += ["", "<b>2) Top 'Must Invest' Candidates</b>"]
    if discovery:
        for i, r in enumerate(discovery[:3], 1):
            parts.append(f"{i}. {_line(r)}")
    else:
        parts.append("<i>Discovery layer not active yet (Phase 2).</i>")

    parts += ["", f"<i>{config.safety_banner()}</i>"]
    return "\n".join(parts)


def actionable(recs: Iterable[Recommendation]) -> list[Recommendation]:
    """Recommendations worth attaching an approval button to."""
    tradable = {Action.BUY, Action.ACCUMULATE, Action.REDUCE, Action.SELL}
    return [r for r in recs if r.recommended_action in tradable and r.suggested_qty > 0]


def format_discovery(recs: Iterable[Recommendation], top_n: int | None = None) -> str:
    """
    Telegram message for the Discovery pipeline: ranked stock ideas mined from
    your trusted YouTube channels + financial blogs. Informational only — these
    are research suggestions, not orders.
    """
    recs = list(recs)
    shown = recs[:top_n] if top_n else recs

    parts: list[str] = [
        "🔎 <b>Stock Ideas — from your channels &amp; blogs</b>",
        f"<i>{len(recs)} ticker(s) discussed; showing top {len(shown)}.</i>",
        "",
    ]
    if not shown:
        parts.append("No tickers crossed the mention threshold today.")
    for i, r in enumerate(shown, 1):
        icon = {Flag.RED: "🔴", Flag.GREEN: "🟢", Flag.NEUTRAL: "⚪"}[r.flag]
        parts.append(
            f"<b>{i}. {icon} {r.ticker}</b> — {r.recommended_action.value} "
            f"(sentiment {r.sentiment_score:+.2f})\n    {r.rationale}"
        )

    parts += [
        "",
        "<i>⚠️ Research suggestions only — nothing is traded automatically. "
        "Do your own due diligence.</i>",
    ]
    return "\n".join(parts)
