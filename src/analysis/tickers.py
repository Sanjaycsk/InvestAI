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
    "HINDZINC": ["hindustan zinc", "hzl", "hindzinc"],
    "VAML": ["vedanta aluminium", "vedanta aluminium metal", "vaml"],
    "VOGL": ["vedanta oil and gas", "vedanta oil & gas", "vogl"],
    "VEDPOWER": ["vedanta power", "vedpower"],
    "VISL": ["vedanta iron and steel", "vedanta iron & steel", "visl"],
    "BPCL": ["bpcl", "bharat petroleum", "bharath petroleum"],
    "DLF": ["dlf"],
    "PIDILITIND": ["pidilite", "fevicol"],
    # The rest of the live 26-instrument universe (see AGENT.md). These were
    # missing, so news/transcripts discussing them were silently invisible to
    # the discovery pipeline even though the agent tracks them daily.
    "FEDERALBNK": ["federal bank", "federalbnk"],
    "SUZLON": ["suzlon", "suzlon energy"],
    "WAAREEENER": ["waaree", "waaree energies", "waareeener"],
    "BEL": ["bharat electronics", "bel"],
    "BHEL": ["bhel", "bharat heavy electricals"],
    "GROWWN200": ["growwn200", "groww nifty 200"],
    "GOLDBEES": ["goldbees", "gold bees"],
    "SILVERBEES": ["silverbees", "silver bees"],
}


# symbol -> exact listed company name (so "VEDL" is unambiguously Vedanta Ltd,
# not Vedanta-anything-else). Keep in sync with TICKER_ALIASES.
COMPANY_NAMES: dict[str, str] = {
    "RELIANCE": "Reliance Industries Ltd",
    "TCS": "Tata Consultancy Services Ltd",
    "HDFCBANK": "HDFC Bank Ltd",
    "ICICIBANK": "ICICI Bank Ltd",
    "INFY": "Infosys Ltd",
    "SBIN": "State Bank of India",
    "HINDUNILVR": "Hindustan Unilever Ltd",
    "ITC": "ITC Ltd",
    "BHARTIARTL": "Bharti Airtel Ltd",
    "KOTAKBANK": "Kotak Mahindra Bank Ltd",
    "LT": "Larsen & Toubro Ltd",
    "AXISBANK": "Axis Bank Ltd",
    "BAJFINANCE": "Bajaj Finance Ltd",
    "BAJAJFINSV": "Bajaj Finserv Ltd",
    "ASIANPAINT": "Asian Paints Ltd",
    "MARUTI": "Maruti Suzuki India Ltd",
    "TATAMOTORS": "Tata Motors Ltd",
    "TATASTEEL": "Tata Steel Ltd",
    "SUNPHARMA": "Sun Pharmaceutical Industries Ltd",
    "TITAN": "Titan Company Ltd",
    "WIPRO": "Wipro Ltd",
    "ULTRACEMCO": "UltraTech Cement Ltd",
    "NESTLEIND": "Nestle India Ltd",
    "POWERGRID": "Power Grid Corporation of India Ltd",
    "NTPC": "NTPC Ltd",
    "ONGC": "Oil & Natural Gas Corporation Ltd",
    "COALINDIA": "Coal India Ltd",
    "ADANIENT": "Adani Enterprises Ltd",
    "ADANIPORTS": "Adani Ports & SEZ Ltd",
    "HCLTECH": "HCL Technologies Ltd",
    "TECHM": "Tech Mahindra Ltd",
    "JSWSTEEL": "JSW Steel Ltd",
    "TATAPOWER": "Tata Power Company Ltd",
    "DMART": "Avenue Supermarts Ltd (DMart)",
    "ZOMATO": "Eternal Ltd (formerly Zomato)",
    "PAYTM": "One97 Communications Ltd (Paytm)",
    "IRCTC": "Indian Railway Catering & Tourism Corp Ltd",
    "DIVISLAB": "Divi's Laboratories Ltd",
    "DRREDDY": "Dr. Reddy's Laboratories Ltd",
    "CIPLA": "Cipla Ltd",
    "GRASIM": "Grasim Industries Ltd",
    "HINDALCO": "Hindalco Industries Ltd",
    "VEDL": "Vedanta Ltd",
    "HINDZINC": "Hindustan Zinc Ltd",
    "VAML": "Vedanta Aluminium Metal Ltd",
    "VOGL": "Vedanta Oil & Gas Ltd",
    "VEDPOWER": "Vedanta Power Ltd",
    "VISL": "Vedanta Iron & Steel Ltd",
    "BPCL": "Bharat Petroleum Corporation Ltd",
    "DLF": "DLF Ltd",
    "PIDILITIND": "Pidilite Industries Ltd",
    "FEDERALBNK": "The Federal Bank Ltd",
    "SUZLON": "Suzlon Energy Ltd",
    "WAAREEENER": "Waaree Energies Ltd",
    "BEL": "Bharat Electronics Ltd",
    "BHEL": "Bharat Heavy Electricals Ltd",
    "GROWWN200": "Groww Nifty 200 ETF",
    "GOLDBEES": "Nippon India ETF Gold BeES",
    "SILVERBEES": "Nippon India ETF Silver BeES",
}


def company_name(symbol: str) -> str:
    """Exact listed company name for an NSE symbol (falls back to the symbol)."""
    return COMPANY_NAMES.get(symbol.upper(), symbol.upper())


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
