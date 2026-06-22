# Hyperliquid Wallet Tracker

> v1.2.0

A Telegram bot that monitors Hyperliquid wallets and sends real-time alerts when positions are opened, closed, increased, decreased, or flipped.

## Features

- Tracks multiple wallets simultaneously
- Alerts on: open, close, increase, decrease, and flip events
- `/active_trades` — snapshot of all open positions across tracked wallets
- `/my_wallet` — view your personal wallet's positions on demand
- `/trending [days]` — most traded tokens over the last N days (default 7)
- Add/remove wallets at runtime via bot commands
- TP/SL orders shown on alerts and position snapshots with % distance from entry
- Size displayed as `154.3000 HYPE ($10,352.14)`
- Wallet list persisted to `config.json`

## Setup

### 1. Create a Telegram bot

Talk to [@BotFather](https://t.me/BotFather), create a bot, and copy the token.

### 2. Get your chat ID

Send any message to your bot, then open:
```
https://api.telegram.org/bot<TOKEN>/getUpdates
```
Look for `"chat":{"id": <number>}` in the response.

### 3. Create `config.json`

```json
{
  "telegram_token": "YOUR_BOT_TOKEN",
  "telegram_chat_id": 123456789,
  "poll_interval_seconds": 10,
  "wallets": [
    { "address": "0xYOUR_WALLET", "label": "MyWallet" }
  ]
}
```

### 4. Install dependencies

```bash
pip install python-telegram-bot requests
```

### 5. Run

```bash
python main.py
```

## Deploy to ScriptHub (Vultr)

```bash
# On the server
cd /root/ScriptHub/scripts
git clone https://github.com/YOUR_USERNAME/WalletTracker.git

# Create config on the server
nano /root/ScriptHub/scripts/WalletTracker/config.json
```

In the ScriptHub dashboard → **+ Add Script**:

| Field | Value |
|---|---|
| Script path | `/root/ScriptHub/scripts/WalletTracker/main.py` |
| Mode | Continuous |
| Auto-restart | On |

## Bot commands

| Command | Description |
|---|---|
| `/active_trades` | Open positions across all tracked wallets |
| `/wallets` | List tracked wallets |
| `/add_wallet <address> <label>` | Start tracking a wallet |
| `/remove_wallet <label>` | Stop tracking a wallet |
| `/set_my_wallet <address>` | Set your personal wallet |
| `/my_wallet` | View your personal wallet's positions |
| `/trending [days]` | Most traded tokens — default 7d, e.g. `/trending 30` |
| `/help` | Show all commands |

## Config reference

| Field | Type | Default | Description |
|---|---|---|---|
| `telegram_token` | string | required | Bot token from BotFather |
| `telegram_chat_id` | number | required | Your chat ID (only this user can control the bot) |
| `poll_interval_seconds` | number | `10` | How often to poll Hyperliquid |
| `wallets` | array | `[]` | Wallets to track on startup |
| `my_wallet` | string | — | Set via `/set_my_wallet`, used by `/my_wallet` |
