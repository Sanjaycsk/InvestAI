"""
Lightweight NSE ticker recognition.

YouTube creators and blogs say "Reliance", "HDFC Bank", "Tata Motors" — not
"RELIANCE", "HDFCBANK", "TATAMOTORS". This maps common names/aliases to NSE
symbols so we can pre-filter which tickers a piece of content is *about* before
spending an LLM call. It's a curated starter set (large-cap heavy); extend
`TICKER_ALIASES` as your channels cover more names. Claude can still surface
tickers beyond this list during synthesis — this is just the cheap first pass.
"""
from __future__ import annotations

import re

# symbol -> list of lowercase aliases (the symbol itself is added automatically)
TICKER_ALIASES: dict[str, list[str]] = {
    "RELIANCE": ["reliance", "ril", "reliance industries"],
    "TCS": ["tcs", "tata consultancy"],
    "HDFCBANK": ["hdfc bank", "hdfcbank"],
    "ICICIBANK": ["icici bank", "icici"],
    "INFY": ["infosys", "infy"],
    "SBIN": ["sbi", "state bank"],
    "HINDUNILVR": ["hul", "hindustan unilever", "unilever"],
    "ITC": ["itc"],
    "BHARTIARTL": ["bharti airtel", "airtel", "bharti"],
    "KOTAKBANK": ["kotak", "kotak bank", "kotak mahindra"],
    "LT": ["l&t", "larsen", "larsen & toubro", "larsen and toubro"],
    "AXISBANK": ["axis bank", "axis"],
    "BAJFINANCE": ["bajaj finance", "baj fin"],
    "BAJAJFINSV": ["bajaj finserv"],
    "ASIANPAINT": ["asian paints", "asian paint"],
    "MARUTI": ["maruti", "maruti suzuki"],
    "TATAMOTORS": ["tata motors", "tatamotors"],
    "TATASTEEL": ["tata steel", "tatasteel"],
    "SUNPHARMA": ["sun pharma", "sunpharma"],
    "TITAN": ["titan", "titan company"],
    "WIPRO": ["wipro"],
    "ULTRACEMCO": ["ultratech", "ultratech cement"],
    "NESTLEIND": ["nestle", "nestle india"],
    "POWERGRID": ["power grid", "powergrid"],
    "NTPC": ["ntpc"],
    "ONGC": ["ongc", "oil and natural gas"],
    "COALINDIA": ["coal india", "coalindia"],
    "ADANIENT": ["adani enterprises", "adani ent"],
    "ADANIPORTS": ["adani ports", "adani port"],
    "HCLTECH": ["hcl", "hcl tech", "hcl technologies"],
    "TECHM": ["tech mahindra", "techm"],
    "JSWSTEEL": ["jsw steel", "jsw"],
    "TATAPOWER": ["tata power", "tatapower"],
    "DMART": ["dmart", "avenue supermarts", "d-mart"],
    "ZOMATO": ["zomato", "eternal"],
    "PAYTM": ["paytm", "one97"],
    "IRCTC": ["irctc"],
    "DIVISLAB": ["divis", "divi's", "divis lab"],
    "DRREDDY": ["dr reddy", "dr reddy's", "drreddy"],
    "CIPLA": ["cipla"],
    "GRASIM": ["grasim"],
    "HINDALCO": ["hindalco"],
    "VEDL": ["vedanta", "vedl"],
    "DLF": ["dlf"],
    "PIDILITIND": ["pidilite", "fevicol"],
}


def _compile() -> list[tuple[str, re.Pattern]]:
    compiled = []
    for symbol, aliases in TICKER_ALIASES.items():
        names = set(aliases) | {symbol.lower()}
        # Longest aliases first so "tata motors" wins over "tata".
        pattern = "|".join(
            re.escape(n) for n in sorted(names, key=len, reverse=True)
        )
        compiled.append((symbol, re.compile(rf"\b(?:{pattern})\b", re.IGNORECASE)))
    return compiled


_COMPILED = _compile()


def extract_candidates(text: str) -> dict[str, int]:
    """Return {symbol: mention_count} for tickers found in `text`."""
    if not text:
        return {}
    counts: dict[str, int] = {}
    for symbol, pattern in _COMPILED:
        n = len(pattern.findall(text))
        if n:
            counts[symbol] = n
    return counts


def known_symbols() -> set[str]:
    return set(TICKER_ALIASES.keys())
