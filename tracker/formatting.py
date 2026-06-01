from .state import WalletState

SIDE_EMOJI = {"LONG": "🟢", "SHORT": "🔴"}


def _pnl_emoji(pnl: float) -> str:
    return "📈" if pnl >= 0 else "📉"


def _fmt_single_position(coin: str, p: dict, label: str) -> str:
    side_icon = SIDE_EMOJI.get(p["side"], "⚪")
    pnl = p["unrealized_pnl"]
    pnl_icon = _pnl_emoji(pnl)
    pnl_sign = "+" if pnl >= 0 else ""
    return (
        f"{side_icon} <b>{label}</b>  ·  <b>{coin}</b>  ·  {p['side']}  ·  {p['leverage']}x\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📌 Entry   <code>${p['entry_px']:,.2f}</code>\n"
        f"📦 Size    <code>{abs(p['size']):.4f}</code>\n"
        f"{pnl_icon} PnL     <code>{pnl_sign}{pnl:.2f} USD</code>"
    )


def fmt_positions(positions: dict, label: str = "My Wallet") -> str:
    if not positions:
        return f"👻 <b>{label}</b> has no open positions."
    blocks = [f"👤 <b>{label}</b>\n"]
    for coin, p in positions.items():
        blocks.append(_fmt_single_position(coin, p, label))
    return "\n\n".join(blocks)


def fmt_active_trades(state: WalletState, wallets: list[dict]) -> str:
    label_map = {w["address"].lower(): w.get("label", w["address"][:8]) for w in wallets}
    all_pos = state.get_all_positions()
    blocks = ["👁 <b>Active Positions</b>\n"]
    found = False
    for address, positions in all_pos.items():
        label = label_map.get(address, address[:8])
        for coin, p in positions.items():
            found = True
            blocks.append(_fmt_single_position(coin, p, label))
    if not found:
        blocks.append("👻 No open positions found.")
    return "\n\n".join(blocks)


def fmt_event(event: dict, label: str) -> str:
    t = event["type"]
    coin = event["coin"]

    if t == "OPEN":
        p = event["pos"]
        side_icon = SIDE_EMOJI.get(p["side"], "⚪")
        return (
            f"{side_icon} <b>OPENED</b>  ·  <b>{label}</b>  ·  <b>{coin}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📌 Entry   <code>${p['entry_px']:,.2f}</code>\n"
            f"📦 Size    <code>{abs(p['size']):.4f}</code>\n"
            f"⚡ Lev     <code>{p['leverage']}x</code>"
        )
    if t == "CLOSE":
        p = event["old"]
        side_icon = SIDE_EMOJI.get(p["side"], "⚪")
        return (
            f"🏁 <b>CLOSED</b>  ·  <b>{label}</b>  ·  <b>{coin}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📌 Entry was   <code>${p['entry_px']:,.2f}</code>\n"
            f"📦 Size was    <code>{abs(p['size']):.4f}</code>"
        )
    if t == "FLIP":
        p = event["pos"]
        side_icon = SIDE_EMOJI.get(p["side"], "⚪")
        return (
            f"🔄 <b>FLIPPED</b>  ·  <b>{label}</b>  ·  <b>{coin}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{side_icon} Now {p['side']}\n"
            f"📌 Entry   <code>${p['entry_px']:,.2f}</code>\n"
            f"📦 Size    <code>{abs(p['size']):.4f}</code>"
        )
    if t == "INCREASE":
        p, old = event["pos"], event["old"]
        return (
            f"📈 <b>INCREASED</b>  ·  <b>{label}</b>  ·  <b>{coin}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📦 Size    <code>{abs(old['size']):.4f}</code> → <code>{abs(p['size']):.4f}</code>"
        )
    if t == "DECREASE":
        p, old = event["pos"], event["old"]
        return (
            f"📉 <b>DECREASED</b>  ·  <b>{label}</b>  ·  <b>{coin}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📦 Size    <code>{abs(old['size']):.4f}</code> → <code>{abs(p['size']):.4f}</code>"
        )
    return f"❓ Unknown event for {coin}"
