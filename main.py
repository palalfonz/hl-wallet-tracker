import asyncio
import json
import logging
import os
import sys
import time
import traceback
from datetime import datetime
from threading import Thread

from telegram import BotCommand
from telegram.ext import Application, CommandHandler

from tracker.bot import (
    cmd_active_trades,
    cmd_add_wallet,
    cmd_help,
    cmd_my_wallet,
    cmd_remove_wallet,
    cmd_set_my_wallet,
    cmd_trending,
    cmd_wallets,
)
from tracker import __version__
from tracker.poller import poll_loop
from tracker.state import WalletState


def log(msg: str, level: str = "INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{level}] {msg}", flush=True)


def log_error(msg: str):
    log(msg, "ERROR")
    print(f"[ERROR] {msg}", file=sys.stderr, flush=True)


logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

BOT_COMMANDS = [
    BotCommand("active_trades",  "Open positions across all tracked wallets"),
    BotCommand("wallets",        "List tracked wallets"),
    BotCommand("add_wallet",     "Track a new wallet — /add_wallet <address> <label>"),
    BotCommand("remove_wallet",  "Stop tracking a wallet — /remove_wallet <label>"),
    BotCommand("set_my_wallet",  "Set your personal wallet — /set_my_wallet <address>"),
    BotCommand("my_wallet",      "View your open positions"),
    BotCommand("trending",       "Most traded tokens — /trending [days]"),
    BotCommand("help",           "Show all commands"),
]


WATCHDOG_TIMEOUT = 120  # seconds — kill process if no heartbeat


def start_watchdog(heartbeat: list):
    def _watch():
        while True:
            time.sleep(30)
            if time.time() - heartbeat[0] > WATCHDOG_TIMEOUT:
                log("Watchdog: no heartbeat for 2 min — forcing restart", "ERROR")
                os.kill(os.getpid(), 9)
    Thread(target=_watch, daemon=True).start()


def run():
    log(f"Hyperliquid Wallet Tracker v{__version__} starting")

    with open("config.json") as f:
        config = json.load(f)

    token = config["telegram_token"]
    chat_id = str(config["telegram_chat_id"])
    state = WalletState()
    loop_holder: list = [None]

    def send_fn(msg: str):
        loop = loop_holder[0]
        if loop is None:
            return
        asyncio.run_coroutine_threadsafe(
            app.bot.send_message(chat_id=chat_id, text=msg, parse_mode="HTML"),
            loop,
        )

    heartbeat = [time.time()]
    start_watchdog(heartbeat)

    async def post_init(application):
        loop_holder[0] = asyncio.get_running_loop()
        await application.bot.set_my_commands(BOT_COMMANDS)
        Thread(target=poll_loop, args=(config, state, send_fn, heartbeat), daemon=True).start()
        log("Command menu registered")

    app = (
        Application.builder()
        .token(token)
        .post_init(post_init)
        .get_updates_read_timeout(30)
        .get_updates_write_timeout(30)
        .get_updates_connect_timeout(30)
        .get_updates_pool_timeout(30)
        .build()
    )
    app.bot_data["state"] = state
    app.bot_data["config"] = config
    app.bot_data["wallets"] = config["wallets"]

    app.add_handler(CommandHandler("active_trades",  cmd_active_trades))
    app.add_handler(CommandHandler("wallets",        cmd_wallets))
    app.add_handler(CommandHandler("add_wallet",     cmd_add_wallet))
    app.add_handler(CommandHandler("remove_wallet",  cmd_remove_wallet))
    app.add_handler(CommandHandler("set_my_wallet",  cmd_set_my_wallet))
    app.add_handler(CommandHandler("my_wallet",      cmd_my_wallet))
    app.add_handler(CommandHandler("trending",       cmd_trending))
    app.add_handler(CommandHandler("help",           cmd_help))

    event_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(event_loop)

    log("Bot polling started")
    app.run_polling(drop_pending_updates=True, timeout=20)


def main():
    try:
        run()
        sys.exit(0)
    except KeyboardInterrupt:
        log("Stopped by user", "WARN")
        sys.exit(0)
    except Exception:
        log_error("Unhandled exception:")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
