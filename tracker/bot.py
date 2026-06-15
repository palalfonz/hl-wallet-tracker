import json
import logging
from telegram import Update
from telegram.ext import ContextTypes
from . import __version__
from .formatting import fmt_active_trades, fmt_positions
from .hyperliquid import get_positions

log = logging.getLogger(__name__)
CONFIG_PATH = "config.json"


def _save_config(config: dict):
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def _is_authorized(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    allowed = str(context.bot_data["config"].get("telegram_chat_id", ""))
    return str(update.effective_chat.id) == allowed


# ── Watched wallets ──────────────────────────────────────────────────────────

async def cmd_active_trades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update, context):
        return
    try:
        msg = fmt_active_trades(context.bot_data["state"], context.bot_data["wallets"])
        await update.message.reply_text(msg, parse_mode="HTML")
    except Exception as e:
        log.exception("Error in /active_trades")
        await update.message.reply_text(f"Error: {e}")


async def cmd_wallets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update, context):
        return
    try:
        wallets = context.bot_data["wallets"]
        if not wallets:
            await update.message.reply_text("No wallets being tracked.")
            return
        lines = ["Tracked wallets:\n"] + [
            f"• {w.get('label', 'Unlabeled')} — {w['address']}" for w in wallets
        ]
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        log.exception("Error in /wallets")
        await update.message.reply_text(f"Error: {e}")


async def cmd_add_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /add_wallet <address> <label>"""
    if not _is_authorized(update, context):
        return
    try:
        args = context.args
        if len(args) < 2:
            await update.message.reply_text("Usage: /add_wallet <address> <label>")
            return

        address = args[0].lower()
        label = " ".join(args[1:])
        config = context.bot_data["config"]

        # Check duplicate
        if any(w["address"].lower() == address for w in config["wallets"]):
            await update.message.reply_text(f"Wallet {address[:10]}... is already being tracked.")
            return

        new_wallet = {"address": address, "label": label}
        config["wallets"].append(new_wallet)
        context.bot_data["wallets"] = config["wallets"]
        _save_config(config)

        try:
            positions = get_positions(address)
            context.bot_data["state"].seed(address, positions)
        except Exception:
            log.warning("Failed to seed initial positions for %s", address)

        await update.message.reply_text(f"Now tracking {label} ({address[:10]}...)")
        log.info("Added wallet %s (%s)", label, address)
    except Exception as e:
        log.exception("Error in /add_wallet")
        await update.message.reply_text(f"Error: {e}")


async def cmd_remove_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /remove_wallet <label>"""
    if not _is_authorized(update, context):
        return
    try:
        if not context.args:
            await update.message.reply_text("Usage: /remove_wallet <label>")
            return

        label = " ".join(context.args).lower()
        config = context.bot_data["config"]
        before = len(config["wallets"])
        config["wallets"] = [
            w for w in config["wallets"] if w.get("label", "").lower() != label
        ]

        if len(config["wallets"]) == before:
            await update.message.reply_text(f"No wallet with label '{label}' found.")
            return

        context.bot_data["wallets"] = config["wallets"]
        _save_config(config)
        await update.message.reply_text(f"Removed wallet '{label}'.")
        log.info("Removed wallet with label %s", label)
    except Exception as e:
        log.exception("Error in /remove_wallet")
        await update.message.reply_text(f"Error: {e}")


# ── My wallet ────────────────────────────────────────────────────────────────

async def cmd_set_my_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /set_my_wallet <address>"""
    if not _is_authorized(update, context):
        return
    try:
        if not context.args:
            await update.message.reply_text("Usage: /set_my_wallet <address>")
            return

        address = context.args[0].lower()
        config = context.bot_data["config"]
        config["my_wallet"] = address
        _save_config(config)
        await update.message.reply_text(f"Your wallet set to {address[:10]}...")
        log.info("my_wallet set to %s", address)
    except Exception as e:
        log.exception("Error in /set_my_wallet")
        await update.message.reply_text(f"Error: {e}")


async def cmd_my_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update, context):
        return
    try:
        config = context.bot_data["config"]
        address = config.get("my_wallet", "")
        if not address:
            await update.message.reply_text(
                "No wallet set. Use /set_my_wallet <address> first."
            )
            return

        positions = get_positions(address)
        msg = fmt_positions(positions, label="My Wallet")
        await update.message.reply_text(msg, parse_mode="HTML")
    except Exception as e:
        log.exception("Error in /my_wallet")
        await update.message.reply_text(f"Error: {e}")


# ── Help ─────────────────────────────────────────────────────────────────────

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"Hyperliquid Wallet Tracker v{__version__}\n\n"
        "Tracking commands:\n"
        "/active_trades — open positions across all tracked wallets\n"
        "/wallets — list tracked wallets\n"
        "/add_wallet <address> <label> — start tracking a wallet\n"
        "/remove_wallet <label> — stop tracking a wallet\n\n"
        "My wallet:\n"
        "/set_my_wallet <address> — set your personal wallet\n"
        "/my_wallet — view your open positions\n\n"
        "/help — show this message"
    )
    await update.message.reply_text(text)
