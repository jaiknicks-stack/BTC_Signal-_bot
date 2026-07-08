"""Indicator math: EMA, ATR, and CVD (cumulative volume delta) from trades."""


def ema(values: list[float], period: int) -> list[float]:
    """Standard EMA, same value count as input (first `period-1` are None)."""
    if len(values) < period:
        return [None] * len(values)
    k = 2 / (period + 1)
    out = [None] * (period - 1)
    seed = sum(values[:period]) / period
    out.append(seed)
    prev = seed
    for v in values[period:]:
        cur = v * k + prev * (1 - k)
        out.append(cur)
        prev = cur
    return out


def atr(candles: list[dict], period: int) -> list[float]:
    """Average True Range. Same length as candles (first `period` are None)."""
    trs = []
    for i, c in enumerate(candles):
        if i == 0:
            trs.append(c["high"] - c["low"])
            continue
        prev_close = candles[i - 1]["close"]
        tr = max(
            c["high"] - c["low"],
            abs(c["high"] - prev_close),
            abs(c["low"] - prev_close),
        )
        trs.append(tr)

    out = [None] * len(candles)
    if len(trs) < period:
        return out
    seed = sum(trs[:period]) / period
    out[period - 1] = seed
    prev = seed
    for i in range(period, len(trs)):
        cur = (prev * (period - 1) + trs[i]) / period
        out[i] = cur
        prev = cur
    return out


def compute_cvd(trades: list[dict]) -> list[dict]:
    """
    Cumulative volume delta from a list of trades (oldest first).
    Returns a running series: [{"time_ms": ..., "cvd": ...}, ...]
    Buy-side taker volume adds, sell-side taker volume subtracts.
    """
    series = []
    running = 0.0
    for t in trades:
        signed = t["quantity"] if t["side"] == "BUY" else -t["quantity"]
        running += signed
        series.append({"time_ms": t["time_ms"], "cvd": running})
    return series


def cvd_at_or_before(cvd_series: list[dict], time_ms: int) -> float:
    """Latest CVD value at or before a given timestamp (0 if none)."""
    val = 0.0
    for point in cvd_series:
        if point["time_ms"] <= time_ms:
            val = point["cvd"]
        else:
            break
    return val
