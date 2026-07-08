"""
Thin client for Crypto.com Exchange's PUBLIC market data endpoints.
No API key is required for any of these - they're read-only public data.

Docs: https://exchange-docs.crypto.com/exchange/v1/rest-ws/index.html
"""
import time
import logging
import requests

import config

log = logging.getLogger("crypto_api")


def _get(path: str, params: dict) -> dict:
    """GET with retries against the Crypto.com public API."""
    url = f"{config.CRYPTOCOM_BASE_URL}/{path}"
    last_err = None
    for attempt in range(1, config.HTTP_MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=params, timeout=config.HTTP_TIMEOUT_SECONDS)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") not in (0, None):
                raise RuntimeError(f"Crypto.com API error: {data}")
            return data["result"]
        except Exception as e:  # noqa: BLE001 - we want to retry on anything
            last_err = e
            log.warning("Request to %s failed (attempt %d/%d): %s",
                        path, attempt, config.HTTP_MAX_RETRIES, e)
            time.sleep(config.HTTP_RETRY_BACKOFF_SECONDS * attempt)
    raise RuntimeError(f"Giving up on {path} after {config.HTTP_MAX_RETRIES} attempts: {last_err}")


def get_candlesticks(instrument: str, period: str, count: int) -> list[dict]:
    """
    Returns a list of candles, oldest first, each shaped:
    {"open": float, "high": float, "low": float, "close": float,
     "volume": float, "start_time_ms": int}
    """
    result = _get("public/get-candlestick", {
        "instrument_name": instrument,
        "timeframe": period,
        "count": count,
    })
    candles = [
        {
            "open": float(c["o"]),
            "high": float(c["h"]),
            "low": float(c["l"]),
            "close": float(c["c"]),
            "volume": float(c["v"]),
            "start_time_ms": int(c["t"]),
        }
        for c in result["data"]
    ]
    candles.sort(key=lambda c: c["start_time_ms"])
    return candles


def get_recent_trades(instrument: str, count: int) -> list[dict]:
    """
    Returns recent public trades, oldest first, each shaped:
    {"side": "BUY"|"SELL", "price": float, "quantity": float, "time_ms": int}
    """
    result = _get("public/get-trades", {
        "instrument_name": instrument,
        "count": count,
    })
    trades = [
        {
            "side": t["s"],
            "price": float(t["p"]),
            "quantity": float(t["q"]),
            "time_ms": int(t["t"]),
        }
        for t in result["data"]
    ]
    trades.sort(key=lambda t: t["time_ms"])
    return trades
