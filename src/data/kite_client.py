"""
Zerodha Kite Connect wrapper.

Responsibilities:
  * read-only: fetch current holdings + live LTP (Phase 1)
  * write: place orders (Phase 3, only via execution layer + double toggle)

IMPORTANT operational note — the Kite access token EXPIRES every morning
(~06:00 IST). There is no fully headless official refresh: you complete a login
flow (request_token via browser redirect -> session checksum), optionally with
TOTP. `print_login_instructions()` documents that; `build_access_token()` shows
the checksum step. In DUMMY_MODE none of this runs and a fixed sample portfolio
is returned so the rest of the system is fully exercisable offline.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Optional

from config import config

log = logging.getLogger(__name__)


@dataclass
class Holding:
    symbol: str
    exchange: str
    quantity: int
    average_price: float
    last_price: float = 0.0

    @property
    def pnl_pct(self) -> Optional[float]:
        if not self.average_price:
            return None
        return (self.last_price - self.average_price) / self.average_price * 100.0


# A fixed, realistic-looking sample portfolio used only in DUMMY_MODE.
_DUMMY_HOLDINGS = [
    Holding("RELIANCE", "NSE", 15, 2450.0),
    Holding("TCS", "NSE", 8, 3520.0),
    Holding("HDFCBANK", "NSE", 25, 1480.0),
    Holding("INFY", "NSE", 30, 1320.0),
    Holding("ITC", "NSE", 100, 410.0),
    Holding("TATAMOTORS", "NSE", 40, 920.0),
]


class KiteClient:
    """Thin wrapper. Honours DUMMY_MODE for every outward call."""

    def __init__(self) -> None:
        self._kite = None
        if not config.DUMMY_MODE:
            self._connect()

    # ---- connection -------------------------------------------------
    def _connect(self) -> None:
        from kiteconnect import KiteConnect

        if not config.KITE_API_KEY:
            raise RuntimeError("KITE_API_KEY missing; set it in config/.env.")
        self._kite = KiteConnect(api_key=config.KITE_API_KEY)
        if config.KITE_ACCESS_TOKEN:
            self._kite.set_access_token(config.KITE_ACCESS_TOKEN)
        else:
            log.warning(
                "No KITE_ACCESS_TOKEN set. Run the daily login flow "
                "(see print_login_instructions) before fetching live data."
            )

    # ---- read-only --------------------------------------------------
    def get_holdings(self) -> list[Holding]:
        """Current equity holdings. Returns the sample portfolio in DUMMY_MODE."""
        if config.DUMMY_MODE:
            log.info("DUMMY_MODE: returning sample portfolio (%d holdings).",
                     len(_DUMMY_HOLDINGS))
            return [Holding(**vars(h)) for h in _DUMMY_HOLDINGS]

        raw = self._kite.holdings()  # type: ignore[union-attr]
        return [
            Holding(
                symbol=h["tradingsymbol"],
                exchange=h.get("exchange", "NSE"),
                quantity=int(h.get("quantity", 0)),
                average_price=float(h.get("average_price", 0.0)),
                last_price=float(h.get("last_price", 0.0)),
            )
            for h in raw
        ]

    def get_ltp(self, symbol: str, exchange: str = "NSE") -> Optional[float]:
        """Live last-traded price — used to re-validate at execution time."""
        if config.DUMMY_MODE:
            from src.data.price_data import latest_price
            return latest_price(symbol, exchange)
        key = f"{exchange}:{symbol}"
        data = self._kite.ltp([key])  # type: ignore[union-attr]
        return float(data[key]["last_price"]) if key in data else None

    # ---- write (Phase 3 — invoked ONLY by the execution layer) ------
    def place_order(self, *, symbol: str, exchange: str, side: str,
                    quantity: int, product: str = "CNC",
                    order_type: str = "MARKET") -> str:
        """
        Place a real order. Never call this directly — go through
        src.execution.order_manager, which enforces the safety toggles.
        """
        if config.DUMMY_MODE:
            raise RuntimeError("place_order called in DUMMY_MODE — refusing.")
        order_id = self._kite.place_order(  # type: ignore[union-attr]
            variety="regular",
            tradingsymbol=symbol,
            exchange=exchange,
            transaction_type=side,           # "BUY" / "SELL"
            quantity=quantity,
            product=product,
            order_type=order_type,
        )
        return str(order_id)


# ---- daily login helpers (documentation / semi-automation) ----------
def build_access_token(request_token: str) -> str:
    """
    Exchange a request_token (from the login redirect) for an access token.
    checksum = SHA256(api_key + request_token + api_secret).
    """
    from kiteconnect import KiteConnect

    kite = KiteConnect(api_key=config.KITE_API_KEY)
    data = kite.generate_session(request_token, api_secret=config.KITE_API_SECRET)
    return data["access_token"]


def print_login_instructions() -> None:
    print(
        "Zerodha daily login:\n"
        f"  1. Open: https://kite.zerodha.com/connect/login?api_key={config.KITE_API_KEY or '<API_KEY>'}&v=3\n"
        "  2. After login you are redirected to your redirect URL with ?request_token=...\n"
        "  3. Call build_access_token(request_token) and store the result in KITE_ACCESS_TOKEN.\n"
        "  (Optional: automate the TOTP step with pyotp + KITE_TOTP_SECRET.)"
    )
    # `hashlib` is imported for the checksum the SDK computes internally.
    _ = hashlib  # keep import meaningful for readers extending this flow
