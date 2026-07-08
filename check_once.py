"""
Single-cycle entry point, built for GitHub Actions (or any cron-style
scheduler) rather than a long-running process. Runs exactly one check,
then exits. State (bot_state.json) is loaded/saved on disk so the workflow
can commit it back to the repo between runs to avoid duplicate alerts.

Run:
    python check_once.py
"""
import logging
import sys

import main as bot_main
import state

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("check_once")


def run():
    bot_state = state.load_state()
    bot_state = bot_main.run_once(bot_state)
    state.save_state(bot_state)


if __name__ == "__main__":
    try:
        run()
    except Exception as e:  # noqa: BLE001
        log.error("Fatal error during check: %s", e, exc_info=True)
        sys.exit(1)
