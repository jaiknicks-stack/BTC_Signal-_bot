"""
Configuration for the BTC signal bot.
Secrets (Telegram token/chat id) are read from environment variables -
see .env.example for the required keys.
"""
import os

# ---------------------------------------------------------------------------
# Instrument / data source
# ---------------------------------------------------------------------------
# Crypto.com perpetual instrument name. Use "BTCUSD-PERP" for the continuous
# perp (closest match to trading BTCUSD on leverage). Swap to "BTC_USDT" if
# you'd rather track spot.
INSTRUMENT = os.getenv("INSTRUMENT", "BTCUSD-PERP")

CRYPTOCOM_BASE_URL = "https://api.crypto.com/exchange/v1"

# ---------------------------------------------------------------------------
# Timeframes (mirrors your manual workflow: 4H bias -> 15m sweep -> 5m entry)
# ---------------------------------------------------------------------------
HTF_PERIOD = "H4"     # higher timeframe trend filter
MTF_PERIOD = "M15"    # liquidity sweep identification
LTF_PERIOD = "M5"     # entry timing / CVD confirmation

HTF_CANDLE_COUNT = 100
MTF_CANDLE_COUNT = 100
LTF_CANDLE_COUNT = 100

# How many recent trades to pull for the CVD window on the LTF chart.
CVD_TRADE_COUNT = 1000

# ---------------------------------------------------------------------------
# Indicator settings
# ---------------------------------------------------------------------------
EMA_FAST = 20
EMA_SLOW = 50
ATR_PERIOD = 14

# ---------------------------------------------------------------------------
# Signal / risk settings
# ---------------------------------------------------------------------------
# Stop is placed just beyond the liquidity-sweep wick, padded by this many ATRs
STOP_ATR_PADDING = 0.25

# Reward:risk target used to compute the take-profit level
REWARD_RISK_RATIO = 2.0

# Risk per trade as a percent of account balance (used only for the position
# sizing line in the alert - purely informational, does not place orders).
RISK_PER_TRADE_PCT = float(os.getenv("RISK_PER_TRADE_PCT", "1.0"))
ACCOUNT_BALANCE_USD = float(os.getenv("ACCOUNT_BALANCE_USD", "0"))  # 0 = omit sizing line

# ---------------------------------------------------------------------------
# Polling
# ---------------------------------------------------------------------------
# How often the bot checks for a new setup, in seconds. 60-120s is plenty
# since the fastest timeframe we act on is 5m.
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))

# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ---------------------------------------------------------------------------
# State file (prevents duplicate alerts for the same setup)
# ---------------------------------------------------------------------------
STATE_FILE = os.getenv("STATE_FILE", "bot_state.json")

# HTTP request settings
HTTP_TIMEOUT_SECONDS = 10
HTTP_MAX_RETRIES = 3
HTTP_RETRY_BACKOFF_SECONDS = 2
