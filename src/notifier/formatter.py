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
from src.analysis.tickers import company_name


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
    icon = {Flag.RED: "🔴", Flag.GREEN: "🟢", Flag.NEUTRAL: "⚪"}

    # Buy/accumulate ideas (positive) vs avoid/exit calls (red). Show both — a
    # "don't touch / get out" signal is as decision-useful as a buy idea.
    positive = [r for r in recs if r.flag in (Flag.GREEN, Flag.NEUTRAL)]
    red = [r for r in recs if r.flag is Flag.RED]
    top = positive[:top_n] if top_n else positive

    def _idea(i: int, r: Recommendation) -> str:
        return (
            f"<b>{i}. {icon[r.flag]} {r.ticker}</b> — {company_name(r.ticker)} — "
            f"{r.recommended_action.value} (sentiment {r.sentiment_score:+.2f})\n"
            f"    {r.rationale}"
        )

    parts: list[str] = [
        "🔎 <b>Stock Ideas — from your channels &amp; blogs</b>",
        f"<i>{len(recs)} ticker(s) discussed.</i>",
        "",
        f"<b>✅ Ideas to consider ({len(top)})</b>",
    ]
    if top:
        parts += [_idea(i, r) for i, r in enumerate(top, 1)]
    else:
        parts.append("<i>No positive ideas crossed the threshold today.</i>")

    parts += ["", f"<b>🔴 Avoid / exit if held ({len(red)})</b>"]
    if red:
        parts += [_idea(i, r) for i, r in enumerate(red, 1)]
    else:
        parts.append("<i>No negative signals today.</i>")

    parts += [
        "",
        "<i>⚠️ Research suggestions only — nothing is traded automatically. "
        "Do your own due diligence.</i>",
    ]
    return "\n".join(parts)
