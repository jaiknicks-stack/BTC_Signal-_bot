# BTC Signal Bot

A standalone Python bot that watches BTCUSD-PERP on Crypto.com's public market
data feed and pushes trade-idea alerts to Telegram. It runs entirely outside
TradingView — you host it (a VPS, a Raspberry Pi, your own machine).

## How it decides on a setup

1. **4H trend bias** — EMA20 vs EMA50 on the 4-hour chart. Price above both,
   fast above slow = bullish (long-only). Reverse = bearish (short-only).
   Anything else = no trade.
2. **15m liquidity sweep** — scans recent 15m candles for a wick through the
   high or low of the prior completed 4H candle that closes back inside the
   range, and only counts it if it lines up with the 4H bias (e.g. a sweep of
   the low only matters in a bullish bias).
3. **5m CVD confirmation** — pulls recent trades (Crypto.com's public trade
   feed includes taker side), builds a real cumulative volume delta, and
   checks for absorption: price makes a new extreme but CVD does *not* confirm
   it, plus a 5m candle closing back through the sweep candle's close.

If all three line up, it computes entry/stop/target off ATR and your
configured reward:risk, and pushes one Telegram message. It won't re-alert the
same sweep twice (tracked in `bot_state.json`).

**This is a rules-based approximation of your manual ICT-style workflow, not
a backtested or guaranteed-profitable system.** Treat every alert as a
starting point for your own chart check, not an auto-trade signal — especially
at high leverage.

## 1. Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 2. Create a Telegram bot (one-time, ~2 minutes)

1. In Telegram, message **@BotFather**.
2. Send `/newbot`, give it a name and a username (must end in `bot`, e.g.
   `jai_btc_signals_bot`).
3. BotFather replies with a token that looks like
   `123456789:AAExampleTokenHere` — this is your `TELEGRAM_BOT_TOKEN`.
4. Now get your chat ID: message **@userinfobot** (just send it anything) and
   it replies with your numeric ID — this is your `TELEGRAM_CHAT_ID`.
5. Send your new bot **any message first** (e.g. "hi") — Telegram bots can't
   message you until you've messaged them at least once.

## 3. Configure

```bash
cp .env.example .env
# edit .env and fill in TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
export $(cat .env | xargs)
```

Tune `config.py` if you want different EMA lengths, reward:risk, or polling
frequency.

## 4. Run

```bash
python main.py
```

You should see log lines every polling cycle ("No setup right now." or an
alert being sent). Leave it running — it's a loop, not a one-shot script.

## 5. Deploy so it runs continuously

Pick whichever fits how you already operate:

**Option A — tmux/screen on a VPS (simplest)**
```bash
tmux new -s btcbot
source venv/bin/activate && export $(cat .env | xargs) && python main.py
# Ctrl+B then D to detach; `tmux attach -t btcbot` to check on it later
```

**Option B — systemd (auto-restarts on crash/reboot)**
```bash
sudo cp btc-signal-bot.service.example /etc/systemd/system/btc-signal-bot.service
# edit paths inside to match where you deployed the code
sudo systemctl daemon-reload
sudo systemctl enable --now btc-signal-bot
sudo journalctl -u btc-signal-bot -f   # to watch logs
```

**Option C — Docker**
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "main.py"]
```
```bash
docker build -t btc-signal-bot .
docker run -d --env-file .env --name btc-signal-bot btc-signal-bot
```

A cheap VPS (DigitalOcean/Linode/Hetzner, ~$5/mo) with systemd is the most
"set and forget" option — a laptop that sleeps will miss cycles.

## Files

| File | Purpose |
|---|---|
| `config.py` | All tunable parameters |
| `crypto_api.py` | Crypto.com public REST client (candles + trades) |
| `indicators.py` | EMA, ATR, CVD math |
| `signals.py` | The actual strategy logic |
| `telegram_notify.py` | Formats and sends the Telegram alert |
| `state.py` | Prevents duplicate alerts |
| `main.py` | The polling loop |
| `test_signals.py` | Offline sanity tests (no network) — `python test_signals.py` |

## Known limitations / things to sanity-check yourself

- **No auth needed** for the Crypto.com endpoints used here — they're public
  market data, so there's no API key to manage, but also no execution: this
  bot only *alerts*, it never places orders.
- The "4H anchor range" here is simply the most recently completed 4H candle,
  not specifically the 5am candle you use manually — if that distinction
  matters to your edge, tell me and I'll adjust `get_anchor_range()` to lock
  to a specific UTC hour instead.
- CVD is computed from recent public trades only (default: last 1000 trades),
  not a full session — fine for the 5m confirmation window this uses, but it
  isn't a persistent CVD chart like TradingView's.
- If Crypto.com's API renames `BTCUSD-PERP` or changes response shape, check
  `crypto_api.py` first — exchange APIs do change.
- Consider paper-tracking alerts for a while before sizing real leverage off
  them.
