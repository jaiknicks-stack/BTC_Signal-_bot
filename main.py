"""
BTC signal bot - entry point.

Polls Crypto.com's public market data on a loop, runs the signal engine,
and pushes a Telegram alert whenever a new setup is confirmed.

Run:
    python main.py
"""
import logging
import time
import sys

import config
import crypto_api
import indicators
import signals
import state
import telegram_notify

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("main")


def run_once(bot_state: dict) -> dict:
    htf_candles = crypto_api.get_candlesticks(config.INSTRUMENT, config.HTF_PERIOD, config.HTF_CANDLE_COUNT)
    mtf_candles = crypto_api.get_candlesticks(config.INSTRUMENT, config.MTF_PERIOD, config.MTF_CANDLE_COUNT)
    ltf_candles = crypto_api.get_candlesticks(config.INSTRUMENT, config.LTF_PERIOD, config.LTF_CANDLE_COUNT)
    trades = crypto_api.get_recent_trades(config.INSTRUMENT, config.CVD_TRADE_COUNT)
    cvd_series = indicators.compute_cvd(trades)

    signal = signals.build_signal(htf_candles, mtf_candles, ltf_candles, cvd_series)

    if signal is None:
        log.info("No setup right now.")
        return bot_state

    if bot_state.get("last_alerted_sweep_time_ms") == signal.sweep_time_ms:
        log.info("Setup already alerted for this sweep (%s), skipping.", signal.sweep_time_ms)
        return bot_state

    message = telegram_notify.format_signal_message(signal)
    sent = telegram_notify.send_telegram_message(message)
    if sent:
        log.info("Alert sent: %s @ %.1f", signal.side, signal.entry)
        bot_state["last_alerted_sweep_time_ms"] = signal.sweep_time_ms
    else:
        log.error("Signal found but Telegram send failed - will retry next cycle.")

    return bot_state


def main():
    log.info("Starting BTC signal bot for %s (poll every %ds)",
              config.INSTRUMENT, config.POLL_INTERVAL_SECONDS)

    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        log.warning("Telegram is not configured yet - set TELEGRAM_BOT_TOKEN and "
                     "TELEGRAM_CHAT_ID (see README) or alerts will only be logged, not sent.")

    bot_state = state.load_state()

    while True:
        try:
            bot_state = run_once(bot_state)
            state.save_state(bot_state)
        except Exception as e:  # noqa: BLE001 - keep the loop alive no matter what
            log.error("Error during cycle: %s", e, exc_info=True)
        time.sleep(config.POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Stopped by user.")
        sys.exit(0)
