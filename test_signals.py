"""
Sanity tests using synthetic candle/trade data (no network needed).
Run: python test_signals.py
"""
import indicators
import signals


def make_candle(t, o, h, l, c, v=10):
    return {"open": o, "high": h, "low": l, "close": c, "volume": v, "start_time_ms": t}


def test_ema_basic():
    vals = [float(i) for i in range(1, 61)]
    out = indicators.ema(vals, 20)
    assert out[18] is None
    assert out[19] is not None
    assert abs(out[-1] - vals[-1]) < 15  # EMA trails a rising series by ~(period/2)
    print("test_ema_basic OK")


def test_bullish_bias_uptrend():
    # Steadily rising closes -> EMA20 > EMA50, close above both
    candles = [make_candle(i, 100 + i, 100 + i + 1, 100 + i - 1, 100 + i) for i in range(1, 80)]
    bias = signals.get_htf_bias(candles)
    assert bias == "BULLISH", bias
    print("test_bullish_bias_uptrend OK")


def test_liquidity_sweep_and_confirmation_long():
    # Build an uptrend on HTF
    htf = [make_candle(i * 14400_000, 100 + i, 100 + i + 1, 100 + i - 1, 100 + i) for i in range(1, 80)]
    anchor = signals.get_anchor_range(htf)  # anchor low ~ (last-2)-1

    # MTF: mostly flat candles, then one candle sweeps below anchor low and closes back above it
    base = htf[-1]["close"]
    mtf = [make_candle(i * 900_000, base, base + 1, base - 1, base) for i in range(1, 15)]
    sweep_low = anchor["low"] - 5
    sweep_candle = make_candle(15 * 900_000, base, base + 1, sweep_low, base - 0.5)
    mtf.append(sweep_candle)

    sweep = signals.find_liquidity_sweep(mtf, anchor, "BULLISH")
    assert sweep is not None
    assert sweep["direction"] == "LONG"
    print("sweep found:", sweep["start_time_ms"], sweep["low"])

    # LTF: candles since sweep time. First candle re-tests the low without
    # breaking it (no new CVD extreme), second candle confirms with a strong close.
    ltf = [
        make_candle(sweep["start_time_ms"], base - 0.5, base, sweep_low + 1, base - 0.3),
        make_candle(sweep["start_time_ms"] + 300_000, base - 0.3, base + 2, base - 0.4, base + 1.5),
    ]

    # Trades: heavy selling into the sweep (already priced in before sweep_time),
    # then buyers stepping in after - CVD should recover, not make a new low.
    trades = []
    t = sweep["start_time_ms"] - 600_000
    for _ in range(20):
        trades.append({"side": "SELL", "price": sweep_low, "quantity": 1, "time_ms": t})
        t += 10_000
    # after the sweep, buyers dominate
    t = sweep["start_time_ms"] + 10_000
    for _ in range(30):
        trades.append({"side": "BUY", "price": base, "quantity": 1, "time_ms": t})
        t += 10_000

    cvd_series = indicators.compute_cvd(trades)
    confirmation = signals.confirm_with_cvd_and_price(ltf, cvd_series, sweep)
    assert confirmation is not None, "expected confirmation"
    print("confirmation:", confirmation)

    sig = signals.build_signal(htf, mtf, ltf, cvd_series)
    assert sig is not None
    assert sig.side == "LONG"
    assert sig.stop < sig.entry < sig.target
    print("signal:", sig)
    print("test_liquidity_sweep_and_confirmation_long OK")


def test_no_signal_when_neutral():
    # Perfectly flat market -> EMAs converge to the same flat price -> NEUTRAL
    candles = [make_candle(i, 100, 101, 99, 100) for i in range(1, 80)]
    bias = signals.get_htf_bias(candles)
    assert bias == "NEUTRAL"
    sig = signals.build_signal(candles, candles, candles, [])
    assert sig is None
    print("test_no_signal_when_neutral OK")


if __name__ == "__main__":
    test_ema_basic()
    test_bullish_bias_uptrend()
    test_liquidity_sweep_and_confirmation_long()
    test_no_signal_when_neutral()
    print("\nAll tests passed.")
