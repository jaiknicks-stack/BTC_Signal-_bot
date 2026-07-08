"""Push messages to Telegram via the Bot API."""
import logging
import requests

import config
from signals import TradeSignal

log = logging.getLogger("telegram_notify")


def _position_size_line(risk_amount_per_unit: float) -> str:
    if config.ACCOUNT_BALANCE_USD <= 0:
        return ""
    risk_usd = config.ACCOUNT_BALANCE_USD * (config.RISK_PER_TRADE_PCT / 100)
    size = risk_usd / risk_amount_per_unit if risk_amount_per_unit > 0 else 0
    return f"\nSuggested size: ~{size:.4f} BTC (risking ${risk_usd:.2f} = {config.RISK_PER_TRADE_PCT}% of ${config.ACCOUNT_BALANCE_USD:.0f})"


def format_signal_message(signal: TradeSignal) -> str:
    risk_per_unit = abs(signal.entry - signal.stop)
    emoji = "🟢" if signal.side == "LONG" else "🔴"
    lines = [
        f"{emoji} {signal.side} setup — {config.INSTRUMENT}",
        "",
        f"HTF bias: {signal.htf_bias}",
        f"Entry:  {signal.entry:.1f}",
        f"Stop:   {signal.stop:.1f}",
        f"Target: {signal.target:.1f}",
        f"R:R:    1:{signal.rr:.1f}",
        "",
        signal.reasoning,
    ]
    sizing = _position_size_line(risk_per_unit)
    if sizing:
        lines.append(sizing)
    lines.append("\nNot financial advice — verify against the chart before acting.")
    return "\n".join(lines)


def send_telegram_message(text: str) -> bool:
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        log.error("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set - cannot send alert.")
        return False

    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id": config.TELEGRAM_CHAT_ID,
            "text": text,
        }, timeout=config.HTTP_TIMEOUT_SECONDS)
        resp.raise_for_status()
        return True
    except Exception as e:  # noqa: BLE001
        log.error("Failed to send Telegram message: %s", e)
        return False
