from collections import Counter
from .state import WalletState

SIDE_EMOJI = {"LONG": "🟢", "SHORT": "🔴"}


def _pnl_emoji(pnl: float) -> str:
    return "📈" if pnl >= 0 else "📉"


def _pct(price: float, entry: float, side: str) -> str:
    if entry == 0:
        return "?"
    pct = (price - entry) / entry * 100
    if side == "SHORT":
        pct = -pct
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.2f}%"


def _fmt_orders(entry_px: float, side: str, orders: dict | None) -> str:
    if not orders:
        return ""
    lines = []
    tps = orders.get("tp", [])
    sl = orders.get("sl")
    for i, tp in enumerate(tps, 1):
        label = f"TP{i}" if len(tps) > 1 else "TP "
        pct = _pct(tp, entry_px, side)
        lines.append(f"🎯 {label}     <code>${tp:,.2f}  ({pct})</code>")
    if sl is not None:
        pct = _pct(sl, entry_px, side)
        lines.append(f"🛑 SL      <code>${sl:,.2f}  ({pct})</code>")
    return "\n" + "\n".join(lines) if lines else ""


def _fmt_single_position(coin: str, p: dict, label: str, orders: dict | None = None) -> str:
    side_icon = SIDE_EMOJI.get(p["side"], "⚪")
    pnl = p["unrealized_pnl"]
    pnl_icon = _pnl_emoji(pnl)
    pnl_sign = "+" if pnl >= 0 else ""
    usd = p.get("position_value", 0)
    usd_str = f"  <code>(${usd:,.2f})</code>" if usd else ""
    leverage = p.get("leverage", 1) or 1
    margin = usd / leverage if usd else 0
    pnl_pct = f"  <code>({pnl_sign}{pnl / margin * 100:.2f}%)</code>" if margin else ""
    orders_str = _fmt_orders(p["entry_px"], p["side"], orders)
    return (
        f"{side_icon} <b>{label}</b>  ·  <b>{coin}</b>  ·  {p['side']}  ·  {p['leverage']}x\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📌 Entry   <code>${p['entry_px']:,.2f}</code>\n"
        f"📦 Size    <code>{abs(p['size']):.4f} {coin}</code>{usd_str}\n"
        f"{pnl_icon} PnL     <code>{pnl_sign}{pnl:.2f} USD</code>{pnl_pct}"
        f"{orders_str}"
    )


def fmt_positions(positions: dict, label: str = "My Wallet", orders: dict | None = None) -> str:
    if not positions:
        return f"👻 <b>{label}</b> has no open positions."
    blocks = [f"👤 <b>{label}</b>\n"]
    for coin, p in positions.items():
        blocks.append(_fmt_single_position(coin, p, label, orders.get(coin) if orders else None))
    return "\n\n".join(blocks)


def fmt_active_trades(state: WalletState, wallets: list[dict], all_orders: dict | None = None) -> str:
    label_map = {w["address"].lower(): w.get("label", w["address"][:8]) for w in wallets}
    all_pos = state.get_all_positions()
    blocks = ["👁 <b>Active Positions</b>\n"]
    found = False
    for address, positions in all_pos.items():
        label = label_map.get(address, address[:8])
        orders = (all_orders or {}).get(address, {})
        for coin, p in positions.items():
            found = True
            blocks.append(_fmt_single_position(coin, p, label, orders.get(coin)))
    if not found:
        blocks.append("👻 No open positions found.")
    return "\n\n".join(blocks)


def fmt_event(event: dict, label: str, orders: dict | None = None) -> str:
    t = event["type"]
    coin = event["coin"]

    if t == "OPEN":
        p = event["pos"]
        side_icon = SIDE_EMOJI.get(p["side"], "⚪")
        usd = p.get("position_value", 0)
        usd_str = f"  <code>(${usd:,.2f})</code>" if usd else ""
        orders_str = _fmt_orders(p["entry_px"], p["side"], orders)
        return (
            f"{side_icon} <b>OPENED</b>  ·  <b>{label}</b>  ·  <b>{coin}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📌 Entry   <code>${p['entry_px']:,.2f}</code>\n"
            f"📦 Size    <code>{abs(p['size']):.4f} {coin}</code>{usd_str}\n"
            f"⚡ Lev     <code>{p['leverage']}x</code>"
            f"{orders_str}"
        )
    if t == "CLOSE":
        p = event["old"]
        side_icon = SIDE_EMOJI.get(p["side"], "⚪")
        usd = p.get("position_value", 0)
        usd_str = f"  <code>(${usd:,.2f})</code>" if usd else ""
        return (
            f"🏁 <b>CLOSED</b>  ·  <b>{label}</b>  ·  <b>{coin}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📌 Entry was   <code>${p['entry_px']:,.2f}</code>\n"
            f"📦 Size was    <code>{abs(p['size']):.4f} {coin}</code>{usd_str}"
        )
    if t == "FLIP":
        p = event["pos"]
        side_icon = SIDE_EMOJI.get(p["side"], "⚪")
        usd = p.get("position_value", 0)
        usd_str = f"  <code>(${usd:,.2f})</code>" if usd else ""
        return (
            f"🔄 <b>FLIPPED</b>  ·  <b>{label}</b>  ·  <b>{coin}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{side_icon} Now {p['side']}\n"
            f"📌 Entry   <code>${p['entry_px']:,.2f}</code>\n"
            f"📦 Size    <code>{abs(p['size']):.4f} {coin}</code>{usd_str}"
        )
    if t == "INCREASE":
        p, old = event["pos"], event["old"]
        usd = p.get("position_value", 0)
        usd_str = f"  <code>(${usd:,.2f})</code>" if usd else ""
        return (
            f"📈 <b>INCREASED</b>  ·  <b>{label}</b>  ·  <b>{coin}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📦 Size    <code>{abs(old['size']):.4f}</code> → <code>{abs(p['size']):.4f} {coin}</code>{usd_str}"
        )
    if t == "DECREASE":
        p, old = event["pos"], event["old"]
        usd = p.get("position_value", 0)
        usd_str = f"  <code>(${usd:,.2f})</code>" if usd else ""
        return (
            f"📉 <b>DECREASED</b>  ·  <b>{label}</b>  ·  <b>{coin}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📦 Size    <code>{abs(old['size']):.4f}</code> → <code>{abs(p['size']):.4f} {coin}</code>{usd_str}"
        )
    return f"❓ Unknown event for {coin}"


def fmt_trending(history: list[dict], days: int) -> str:
    if not history:
        return f"👻 No trades recorded in the last {days}d."
    counts = Counter(e["coin"] for e in history)
    lines = [f"🔥 <b>Trending — last {days}d</b>  ({len(history)} events)\n"]
    for i, (coin, count) in enumerate(counts.most_common(10), 1):
        bar = "▓" * min(count, 10)
        lines.append(f"{i}. <b>{coin}</b>  {bar}  <code>{count}</code>")
    return "\n".join(lines)
