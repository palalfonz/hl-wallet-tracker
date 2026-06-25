import time
import logging
from datetime import datetime, timezone
from .hyperliquid import get_orders, get_positions
from .formatting import fmt_daily_summary, fmt_event, fmt_liq_warning
from .state import WalletState

log = logging.getLogger(__name__)

LIQ_WARN_PCT = 10.0  # warn when mark price is within 10% of liquidation


def _pct_to_liq(p: dict) -> float | None:
    liq_px = p.get("liq_px")
    mark_px = p.get("mark_px")
    if not liq_px or not mark_px:
        return None
    return abs(mark_px - liq_px) / mark_px * 100


def poll_loop(config: dict, state: WalletState, send_fn, heartbeat: list | None = None):
    wallets = config["wallets"]
    interval = config.get("poll_interval_seconds", 10)
    label_map = {w["address"].lower(): w.get("label", w["address"][:8]) for w in wallets}

    for w in wallets:
        try:
            positions = get_positions(w["address"])
            state.seed(w["address"], positions)
            log.info("Seeded %s: %d open position(s)", w.get("label", w["address"]), len(positions))
        except Exception as e:
            log.warning("Failed to seed %s: %s", w["address"], e)

    last_summary_day = datetime.now(timezone.utc).date()
    liq_warned: set[str] = set()  # track coins already warned to avoid spam

    log.info("Polling every %ds for %d wallet(s)…", interval, len(wallets))
    while True:
        time.sleep(interval)
        if heartbeat is not None:
            heartbeat[0] = time.time()

        # Daily summary at midnight UTC
        today = datetime.now(timezone.utc).date()
        if today != last_summary_day:
            try:
                yesterday_start = datetime(last_summary_day.year, last_summary_day.month, last_summary_day.day, tzinfo=timezone.utc)
                history = state.get_history(yesterday_start)
                send_fn(fmt_daily_summary(history, wallets))
            except Exception as e:
                log.warning("Failed to send daily summary: %s", e)
            last_summary_day = today

        for w in wallets:
            addr = w["address"]
            label = label_map.get(addr.lower(), addr[:8])
            try:
                positions = get_positions(addr)
                events = state.update(addr, positions)

                # Liquidation risk check
                for coin, p in positions.items():
                    pct = _pct_to_liq(p)
                    warn_key = f"{addr}:{coin}"
                    if pct is not None and pct <= LIQ_WARN_PCT:
                        if warn_key not in liq_warned:
                            send_fn(fmt_liq_warning(coin, label, p, pct))
                            liq_warned.add(warn_key)
                            log.warning("Liq warning sent for %s %s (%.1f%% away)", label, coin, pct)
                    else:
                        liq_warned.discard(warn_key)

                open_events = [ev for ev in events if ev["type"] == "OPEN"]
                orders = {}
                if open_events:
                    try:
                        orders = get_orders(addr, positions)
                    except Exception as e:
                        log.warning("Failed to fetch orders for %s: %s", addr, e)
                for ev in events:
                    coin_orders = orders.get(ev["coin"]) if ev["type"] == "OPEN" else None
                    send_fn(fmt_event(ev, label, coin_orders))
                    state.log_event(ev, label)
                    log.info("Event [%s] %s %s", ev["type"], label, ev["coin"])
            except Exception as e:
                log.warning("Error polling %s: %s", addr, e)
