"""
Signal engine.

Mirrors the manual workflow this bot is based on:
  1. 4H EMA trend filter sets directional bias (long-only / short-only / no-trade)
  2. 15m: find a liquidity sweep of the prior 4H range (wick through high/low,
     close back inside) that aligns with the 4H bias
  3. 5m: confirm with CVD (does the sweep show absorption, i.e. price makes a
     new extreme but CVD does NOT confirm it) plus a confirmation candle
     closing back through the sweep level

If all three align, emit a TradeSignal with entry/stop/target/R:R.
"""
from dataclasses import dataclass
from typing import Optional

import config
import indicators


@dataclass
class TradeSignal:
    side: str            # "LONG" or "SHORT"
    entry: float
    stop: float
    target: float
    rr: float
    htf_bias: str
    sweep_time_ms: int
    reasoning: str


def get_htf_bias(htf_candles: list[dict]) -> str:
    closes = [c["close"] for c in htf_candles]
    ema_fast = indicators.ema(closes, config.EMA_FAST)
    ema_slow = indicators.ema(closes, config.EMA_SLOW)
    if ema_fast[-1] is None or ema_slow[-1] is None:
        return "NEUTRAL"
    last_close = closes[-1]
    if last_close > ema_fast[-1] > ema_slow[-1]:
        return "BULLISH"
    if last_close < ema_fast[-1] < ema_slow[-1]:
        return "BEARISH"
    return "NEUTRAL"


def get_anchor_range(htf_candles: list[dict]) -> dict:
    """Most recent COMPLETED 4H candle - used as the liquidity reference range."""
    anchor = htf_candles[-2]  # -1 may still be the currently-forming candle
    return {"high": anchor["high"], "low": anchor["low"], "time_ms": anchor["start_time_ms"]}


def find_liquidity_sweep(mtf_candles: list[dict], anchor: dict, htf_bias: str,
                          lookback: int = 20) -> Optional[dict]:
    """
    Scan the most recent `lookback` 15m candles for a sweep of the anchor
    range that aligns with the HTF bias:
      - BULLISH bias -> look for a sweep of the anchor LOW (wick below, close back above)
      - BEARISH bias -> look for a sweep of the anchor HIGH (wick above, close back below)
    Returns the sweeping candle (with a "direction" key) or None.
    """
    if htf_bias == "NEUTRAL":
        return None

    recent = mtf_candles[-lookback:]
    for c in reversed(recent):
        if htf_bias == "BULLISH" and c["low"] < anchor["low"] and c["close"] > anchor["low"]:
            return {**c, "direction": "LONG"}
        if htf_bias == "BEARISH" and c["high"] > anchor["high"] and c["close"] < anchor["high"]:
            return {**c, "direction": "SHORT"}
    return None


def confirm_with_cvd_and_price(ltf_candles: list[dict], cvd_series: list[dict],
                                sweep: dict) -> Optional[dict]:
    """
    After a sweep, look at 5m candles/CVD since the sweep time for:
      - absorption: price extreme not confirmed by a new CVD extreme
      - a confirmation candle closing back through the sweep candle's close
    Returns {"entry": ..., "extreme": ...} or None if not yet confirmed.
    """
    since = [c for c in ltf_candles if c["start_time_ms"] >= sweep["start_time_ms"]]
    if len(since) < 2:
        return None

    direction = sweep["direction"]
    cvd_at_sweep = indicators.cvd_at_or_before(cvd_series, sweep["start_time_ms"])
    latest_cvd = indicators.cvd_at_or_before(cvd_series, since[-1]["start_time_ms"])

    if direction == "LONG":
        extreme = min(c["low"] for c in since)
        # absorption: price is at/near the sweep low but CVD did not make a new low
        cvd_absorbed = latest_cvd >= cvd_at_sweep
        confirmation_candle = since[-1]["close"] > sweep["close"]
        if cvd_absorbed and confirmation_candle:
            return {"entry": since[-1]["close"], "extreme": extreme}
    else:
        extreme = max(c["high"] for c in since)
        cvd_absorbed = latest_cvd <= cvd_at_sweep
        confirmation_candle = since[-1]["close"] < sweep["close"]
        if cvd_absorbed and confirmation_candle:
            return {"entry": since[-1]["close"], "extreme": extreme}

    return None


def build_signal(htf_candles, mtf_candles, ltf_candles, cvd_series) -> Optional[TradeSignal]:
    htf_bias = get_htf_bias(htf_candles)
    if htf_bias == "NEUTRAL":
        return None

    anchor = get_anchor_range(htf_candles)
    sweep = find_liquidity_sweep(mtf_candles, anchor, htf_bias)
    if sweep is None:
        return None

    confirmation = confirm_with_cvd_and_price(ltf_candles, cvd_series, sweep)
    if confirmation is None:
        return None

    ltf_atr = indicators.atr(ltf_candles, config.ATR_PERIOD)
    last_atr = ltf_atr[-1] or (ltf_candles[-1]["high"] - ltf_candles[-1]["low"])
    padding = last_atr * config.STOP_ATR_PADDING

    entry = confirmation["entry"]
    if sweep["direction"] == "LONG":
        stop = confirmation["extreme"] - padding
        risk = entry - stop
        target = entry + risk * config.REWARD_RISK_RATIO
    else:
        stop = confirmation["extreme"] + padding
        risk = stop - entry
        target = entry - risk * config.REWARD_RISK_RATIO

    if risk <= 0:
        return None

    reasoning = (
        f"4H bias {htf_bias} (EMA{config.EMA_FAST}/{config.EMA_SLOW} aligned). "
        f"15m liquidity sweep of prior 4H range at {sweep['low' if sweep['direction']=='LONG' else 'high']:.1f}, "
        f"closed back inside. 5m CVD shows absorption (no new CVD extreme on the price extreme) "
        f"with a confirmation candle closing back through {sweep['close']:.1f}."
    )

    return TradeSignal(
        side=sweep["direction"],
        entry=entry,
        stop=stop,
        target=target,
        rr=config.REWARD_RISK_RATIO,
        htf_bias=htf_bias,
        sweep_time_ms=sweep["start_time_ms"],
        reasoning=reasoning,
    )
