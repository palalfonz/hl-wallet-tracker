import json
import logging
import time
from datetime import datetime, timedelta, timezone
from telegram import Update
from telegram.ext import ContextTypes
from . import __version__
from .formatting import fmt_active_trades, fmt_daily_summary, fmt_positions, fmt_status, fmt_trending
from .hyperliquid import get_orders, get_positions

log = logging.getLogger(__name__)
CONFIG_PATH = "config.json"


def _save_config(config: dict):
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def _is_authorized(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    allowed = str(context.bot_data["config"].get("telegram_chat_id", ""))
    return str(update.effective_chat.id) == allowed


def _is_testnet(config: dict) -> bool:
    return config.get("network", "mainnet") == "testnet"


async def log_incoming(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text:
        log.info("TG ← %s (chat %s)", update.message.text, update.effective_chat.id)


async def _reply(update: Update, cmd: str, text: str, **kwargs):
    try:
        await update.message.reply_text(text, **kwargs)
        log.info("TG → %s OK", cmd)
    except Exception as e:
        log.error("TG → %s FAILED: %s", cmd, e)
        raise


# ── Watched wallets ──────────────────────────────────────────────────────────

async def cmd_active_trades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update, context):
        return
    try:
        wallets = context.bot_data["wallets"]
        testnet = _is_testnet(context.bot_data["config"])
        all_pos = context.bot_data["state"].get_all_positions()
        all_orders = {}
        for w in wallets:
            try:
                addr = w["address"].lower()
                all_orders[addr] = get_orders(w["address"], all_pos.get(addr, {}), testnet=testnet)
            except Exception:
                pass
        msg = fmt_active_trades(context.bot_data["state"], wallets, all_orders)
        await _reply(update, "/active_trades", msg, parse_mode="HTML")
    except Exception as e:
        log.exception("Error in /active_trades")
        await _reply(update, "/active_trades", f"Error: {e}")


async def cmd_wallets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update, context):
        return
    try:
        wallets = context.bot_data["wallets"]
        if not wallets:
            await _reply(update, "/wallets", "No wallets being tracked.")
            return
        lines = ["Tracked wallets:\n"] + [
            f"• {w.get('label', 'Unlabeled')} — {w['address']}" for w in wallets
        ]
        await _reply(update, "/wallets", "\n".join(lines))
    except Exception as e:
        log.exception("Error in /wallets")
        await _reply(update, "/wallets", f"Error: {e}")


async def cmd_add_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /add_wallet <address> <label>"""
    if not _is_authorized(update, context):
        return
    try:
        args = context.args
        if len(args) < 2:
            await _reply(update, "/add_wallet", "Usage: /add_wallet <address> <label>")
            return

        address = args[0].lower()
        label = " ".join(args[1:])
        config = context.bot_data["config"]
        lock = context.bot_data["config_lock"]

        with lock:
            already_tracked = any(w["address"].lower() == address for w in config["wallets"])
            if not already_tracked:
                new_wallet = {"address": address, "label": label}
                config["wallets"] = config["wallets"] + [new_wallet]
                context.bot_data["wallets"] = config["wallets"]
                _save_config(config)

        if already_tracked:
            await _reply(update, "/add_wallet", f"Wallet {address[:10]}... is already being tracked.")
            return

        try:
            positions = get_positions(address, testnet=_is_testnet(config))
            context.bot_data["state"].seed(address, positions)
        except Exception:
            log.warning("Failed to seed initial positions for %s", address)

        await _reply(update, "/add_wallet", f"Now tracking {label} ({address[:10]}...)")
        log.info("Added wallet %s (%s)", label, address)
    except Exception as e:
        log.exception("Error in /add_wallet")
        await _reply(update, "/add_wallet", f"Error: {e}")


async def cmd_remove_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /remove_wallet <label>"""
    if not _is_authorized(update, context):
        return
    try:
        if not context.args:
            await _reply(update, "/remove_wallet", "Usage: /remove_wallet <label>")
            return

        label = " ".join(context.args).lower()
        config = context.bot_data["config"]
        lock = context.bot_data["config_lock"]

        with lock:
            found = any(w.get("label", "").lower() == label for w in config["wallets"])
            if found:
                config["wallets"] = [
                    w for w in config["wallets"] if w.get("label", "").lower() != label
                ]
                context.bot_data["wallets"] = config["wallets"]
                _save_config(config)

        if not found:
            await _reply(update, "/remove_wallet", f"No wallet with label '{label}' found.")
            return

        await _reply(update, "/remove_wallet", f"Removed wallet '{label}'.")
        log.info("Removed wallet with label %s", label)
    except Exception as e:
        log.exception("Error in /remove_wallet")
        await _reply(update, "/remove_wallet", f"Error: {e}")


# ── Network ──────────────────────────────────────────────────────────────────

async def cmd_network(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update, context):
        return
    try:
        network = context.bot_data["config"].get("network", "mainnet")
        await _reply(
            update, "/network",
            f"Current network: <b>{network}</b>\nUse /set_network mainnet or /set_network testnet to switch.",
            parse_mode="HTML",
        )
    except Exception as e:
        log.exception("Error in /network")
        await _reply(update, "/network", f"Error: {e}")


async def cmd_set_network(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /set_network <mainnet|testnet>"""
    if not _is_authorized(update, context):
        return
    try:
        if not context.args or context.args[0].lower() not in ("mainnet", "testnet"):
            await _reply(update, "/set_network", "Usage: /set_network <mainnet|testnet>")
            return

        network = context.args[0].lower()
        config = context.bot_data["config"]
        lock = context.bot_data["config_lock"]

        with lock:
            unchanged = config.get("network", "mainnet") == network
            if not unchanged:
                config["network"] = network
                _save_config(config)

        if unchanged:
            await _reply(update, "/set_network", f"Already on {network}.")
            return

        await _reply(
            update, "/set_network",
            f"Switched to <b>{network}</b>. Re-seeding tracked wallets' positions on the next poll cycle "
            "— no OPEN/CLOSE alerts will fire for the switch itself.",
            parse_mode="HTML",
        )
        log.info("Network switched to %s", network)
    except Exception as e:
        log.exception("Error in /set_network")
        await _reply(update, "/set_network", f"Error: {e}")


# ── My wallet ────────────────────────────────────────────────────────────────

async def cmd_set_my_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /set_my_wallet <address>"""
    if not _is_authorized(update, context):
        return
    try:
        if not context.args:
            await _reply(update, "/set_my_wallet", "Usage: /set_my_wallet <address>")
            return

        address = context.args[0].lower()
        config = context.bot_data["config"]
        config["my_wallet"] = address
        _save_config(config)
        await _reply(update, "/set_my_wallet", f"Your wallet set to {address[:10]}...")
        log.info("my_wallet set to %s", address)
    except Exception as e:
        log.exception("Error in /set_my_wallet")
        await _reply(update, "/set_my_wallet", f"Error: {e}")


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

        testnet = _is_testnet(config)
        positions = get_positions(address, testnet=testnet)
        try:
            orders = get_orders(address, positions, testnet=testnet)
        except Exception:
            orders = {}
        msg = fmt_positions(positions, label="My Wallet", orders=orders)
        await _reply(update, "/my_wallet", msg, parse_mode="HTML")
    except Exception as e:
        log.exception("Error in /my_wallet")
        await _reply(update, "/my_wallet", f"Error: {e}")


# ── Trending ─────────────────────────────────────────────────────────────────

async def cmd_trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /trending [days]  — default 7"""
    if not _is_authorized(update, context):
        return
    try:
        days = int(context.args[0]) if context.args else 7
        if days < 1:
            await update.message.reply_text("Days must be at least 1.")
            return
        since = datetime.now(timezone.utc) - timedelta(days=days)
        history = context.bot_data["state"].get_history(since)
        msg = fmt_trending(history, days)
        await _reply(update, "/trending", msg, parse_mode="HTML")
    except ValueError:
        await _reply(update, "/trending", "Usage: /trending [days]  e.g. /trending 30")
    except Exception as e:
        log.exception("Error in /trending")
        await _reply(update, "/trending", f"Error: {e}")


# ── Status ───────────────────────────────────────────────────────────────────

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update, context):
        return
    try:
        uptime = time.time() - context.bot_data["start_time"]
        last_poll_holder = context.bot_data.get("last_poll_holder")
        last_poll = last_poll_holder[0] if last_poll_holder else context.bot_data["start_time"]
        msg = fmt_status(uptime, context.bot_data["wallets"], last_poll)
        await _reply(update, "/status", msg, parse_mode="HTML")
    except Exception as e:
        log.exception("Error in /status")
        await _reply(update, "/status", f"Error: {e}")


# ── Summary ───────────────────────────────────────────────────────────────────

async def cmd_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /summary [address]  — address lookup or today's PnL summary"""
    if not _is_authorized(update, context):
        return
    try:
        if context.args:
            address = context.args[0].lower()
            testnet = _is_testnet(context.bot_data["config"])
            positions = get_positions(address, testnet=testnet)
            try:
                orders = get_orders(address, positions, testnet=testnet)
            except Exception:
                orders = {}
            msg = fmt_positions(positions, label=address[:10] + "...", orders=orders)
            await _reply(update, "/summary", msg, parse_mode="HTML")
        else:
            since = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            history = context.bot_data["state"].get_history(since)
            msg = fmt_daily_summary(history, context.bot_data["wallets"])
            await _reply(update, "/summary", msg, parse_mode="HTML")
    except Exception as e:
        log.exception("Error in /summary")
        await _reply(update, "/summary", f"Error: {e}")


# ── Help ─────────────────────────────────────────────────────────────────────

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"Hyperliquid Wallet Tracker v{__version__}\n\n"
        "Tracking commands:\n"
        "/active_trades — open positions across all tracked wallets\n"
        "/wallets — list tracked wallets\n"
        "/add_wallet <address> <label> — start tracking a wallet\n"
        "/remove_wallet <label> — stop tracking a wallet\n\n"
        "Network:\n"
        "/network — show current network (mainnet/testnet)\n"
        "/set_network <mainnet|testnet> — switch network\n\n"
        "My wallet:\n"
        "/set_my_wallet <address> — set your personal wallet\n"
        "/my_wallet — view your open positions\n\n"
        "/trending [days] — most traded tokens (default 7d)\n"
        "/summary — today's PnL summary\n"
        "/summary <address> — on-demand positions for any address\n"
        "/status — bot uptime and health\n"
        "/help — show this message"
    )
    await _reply(update, "/help", text)
