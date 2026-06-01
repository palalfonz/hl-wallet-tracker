import asyncio
import json
import logging
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
    cmd_wallets,
)
from tracker import __version__
from tracker.poller import poll_loop
from tracker.state import WalletState

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

BOT_COMMANDS = [
    BotCommand("active_trades",  "Open positions across all tracked wallets"),
    BotCommand("wallets",        "List tracked wallets"),
    BotCommand("add_wallet",     "Track a new wallet — /add_wallet <address> <label>"),
    BotCommand("remove_wallet",  "Stop tracking a wallet — /remove_wallet <label>"),
    BotCommand("set_my_wallet",  "Set your personal wallet — /set_my_wallet <address>"),
    BotCommand("my_wallet",      "View your open positions"),
    BotCommand("help",           "Show all commands"),
]


def main():
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

    async def post_init(application):
        loop_holder[0] = asyncio.get_running_loop()
        await application.bot.set_my_commands(BOT_COMMANDS)
        Thread(target=poll_loop, args=(config, state, send_fn), daemon=True).start()
        log.info("Command menu registered.")

    app = Application.builder().token(token).post_init(post_init).build()
    app.bot_data["state"] = state
    app.bot_data["config"] = config
    app.bot_data["wallets"] = config["wallets"]

    app.add_handler(CommandHandler("active_trades",  cmd_active_trades))
    app.add_handler(CommandHandler("wallets",        cmd_wallets))
    app.add_handler(CommandHandler("add_wallet",     cmd_add_wallet))
    app.add_handler(CommandHandler("remove_wallet",  cmd_remove_wallet))
    app.add_handler(CommandHandler("set_my_wallet",  cmd_set_my_wallet))
    app.add_handler(CommandHandler("my_wallet",      cmd_my_wallet))
    app.add_handler(CommandHandler("help",           cmd_help))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    log.info("Hyperliquid Wallet Tracker v%s started.", __version__)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
