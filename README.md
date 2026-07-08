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

### Delivery method: direct Telegram vs. your Pipedream bridge

Set `NOTIFY_METHOD` in `.env`:

- `telegram_direct` (default) — this bot calls the Telegram Bot API itself.
  Simplest, fewest moving parts.
- `pipedream` — this bot POSTs to `PIPEDREAM_WEBHOOK_URL`, the same Pipedream
  workflow your Pine Script alerts already bridge through to Telegram. Set
  `PIPEDREAM_PAYLOAD_FORMAT=text` (default) if that workflow expects a raw
  text body the way TradingView's `alert()` webhook sends it — this is a
  drop-in match. Set it to `json` if you'd rather receive structured fields
  (`side`, `entry`, `stop`, `target`, `rr`, `reasoning`, etc.) and reshape the
  message inside Pipedream instead.
- `both` — sends via both paths independently; if one fails the other can
  still get through.

If your Pipedream workflow expects specific JSON key names that don't match
`notify.py`'s `_pipedream_json_payload()`, that function is the one place to
adjust them.

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

**Option D — GitHub Actions (no server at all, best for iPad-only setups)**

This runs the bot on GitHub's own machines on a schedule — you never manage a
server. Everything below can be done from Safari on an iPad using github.com
directly (no app required), though the GitHub or Working Copy app makes
editing files a bit easier if you prefer.

1. **Create a repo.** On github.com, tap **New repository**. Public repos get
   unlimited free Actions minutes; private repos get 2,000 free minutes/month
   on the Free plan, which is tight at a 5-minute cadence (see note below).
   Nothing secret lives in the code itself — tokens go in encrypted repo
   secrets — so a public repo is safe here if you'd rather not think about
   minute budgets.

2. **Upload all the bot files**, keeping the folder structure, including
   `.github/workflows/signal-check.yml` and `bot_state.json`. On github.com
   you can use **Add file → Upload files** and drag them in, or **Add file →
   Create new file** and type the full path (e.g.
   `.github/workflows/signal-check.yml`) into the filename box — GitHub
   creates the folders for you.

3. **Add your config as repo secrets** — Settings → Secrets and variables →
   Actions → **New repository secret**, one per row:

   | Secret name | Value |
   |---|---|
   | `TELEGRAM_BOT_TOKEN` | from BotFather |
   | `TELEGRAM_CHAT_ID` | from @userinfobot |
   | `NOTIFY_METHOD` | `telegram_direct` (or `pipedream` / `both`) |
   | `PIPEDREAM_WEBHOOK_URL` | leave blank if not using Pipedream |
   | `PIPEDREAM_PAYLOAD_FORMAT` | `text` (or `json`) |
   | `INSTRUMENT` | `BTCUSD-PERP` |
   | `RISK_PER_TRADE_PCT` | `1.0` |
   | `ACCOUNT_BALANCE_USD` | `0` (or your balance) |

   Never commit a real `.env` file to the repo — secrets only, always.

4. **Test it manually** before waiting on the schedule: Actions tab →
   "BTC Signal Check" workflow → **Run workflow** button. Check the run's
   logs to confirm it completed and (if a setup exists) that Telegram
   received the message.

5. It now runs itself on the `*/5 * * * *` cron in
   `.github/workflows/signal-check.yml` — GitHub queues scheduled runs
   during busy periods, so treat "every 5 minutes" as "every 5-15 minutes."
   If you went private and want to stay well under the free-minute budget,
   change that cron line to `*/15 * * * *`.

State (`bot_state.json`) gets committed back by the workflow after every run
so it won't re-alert the same setup, and you'll see a small "update signal
state" commit in the repo's history after each cycle that finds a match —
that's expected, not an error.

## Files

| File | Purpose |
|---|---|
| `config.py` | All tunable parameters |
| `crypto_api.py` | Crypto.com public REST client (candles + trades) |
| `indicators.py` | EMA, ATR, CVD math |
| `signals.py` | The actual strategy logic |
| `telegram_notify.py` | Formats the message + direct Telegram Bot API send |
| `notify.py` | Dispatches to telegram_direct / pipedream / both |
| `state.py` | Prevents duplicate alerts |
| `main.py` | The polling loop (for VPS/systemd/Docker deployments) |
| `check_once.py` | Single-cycle entrypoint (for GitHub Actions / cron) |
| `.github/workflows/signal-check.yml` | GitHub Actions schedule (no server needed) |
| `bot_state.json` | Tracks the last alerted setup — committed back by Actions |
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
