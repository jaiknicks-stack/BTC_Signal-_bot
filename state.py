"""Tiny JSON-file state store so we don't re-alert the same sweep/setup."""
import json
import os
import logging

import config

log = logging.getLogger("state")


def load_state() -> dict:
    if not os.path.exists(config.STATE_FILE):
        return {"last_alerted_sweep_time_ms": None}
    try:
        with open(config.STATE_FILE, "r") as f:
            return json.load(f)
    except Exception as e:  # noqa: BLE001
        log.warning("Could not read state file, starting fresh: %s", e)
        return {"last_alerted_sweep_time_ms": None}


def save_state(state: dict) -> None:
    with open(config.STATE_FILE, "w") as f:
        json.dump(state, f)
