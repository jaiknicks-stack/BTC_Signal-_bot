"""
Unified alert dispatcher. Routes a TradeSignal to whichever delivery
method(s) are configured:
  - telegram_direct: call the Telegram Bot API straight from this bot
  - pipedream:       POST to your existing Pipedream webhook bridge
  - both:            do both, independently (one failing doesn't block the other)
"""
import logging
import time
import requests

import config
import telegram_notify
from signals import TradeSignal

log = logging.getLogger("notify")


def _pipedream_json_payload(signal: TradeSignal, text: str) -> dict:
    return {
        "message": text,
        "instrument": config.INSTRUMENT,
        "side": signal.side,
        "entry": signal.entry,
        "stop": signal.stop,
        "target": signal.target,
        "rr": signal.rr,
        "htf_bias": signal.htf_bias,
        "reasoning": signal.reasoning,
        "sweep_time_ms": signal.sweep_time_ms,
        "sent_at_ms": int(time.time() * 1000),
    }


def send_via_pipedream(signal: TradeSignal, text: str) -> bool:
    if not config.PIPEDREAM_WEBHOOK_URL:
        log.error("PIPEDREAM_WEBHOOK_URL not set - cannot send via Pipedream.")
        return False

    try:
        if config.PIPEDREAM_PAYLOAD_FORMAT == "json":
            resp = requests.post(
                config.PIPEDREAM_WEBHOOK_URL,
                json=_pipedream_json_payload(signal, text),
                timeout=config.HTTP_TIMEOUT_SECONDS,
            )
        else:
            resp = requests.post(
                config.PIPEDREAM_WEBHOOK_URL,
                data=text.encode("utf-8"),
                headers={"Content-Type": "text/plain"},
                timeout=config.HTTP_TIMEOUT_SECONDS,
            )
        resp.raise_for_status()
        return True
    except Exception as e:  # noqa: BLE001
        log.error("Failed to send via Pipedream: %s", e)
        return False


def send_alert(signal: TradeSignal) -> bool:
    """Formats the message once, sends via whichever method(s) are configured.
    Returns True if at least one delivery method succeeded."""
    text = telegram_notify.format_signal_message(signal)
    method = config.NOTIFY_METHOD.lower()
    results = []

    if method in ("telegram_direct", "both"):
        results.append(telegram_notify.send_telegram_message(text))

    if method in ("pipedream", "both"):
        results.append(send_via_pipedream(signal, text))

    if not results:
        log.error("NOTIFY_METHOD=%r doesn't match any known delivery method "
                   "(telegram_direct / pipedream / both).", config.NOTIFY_METHOD)
        return False

    return any(results)
