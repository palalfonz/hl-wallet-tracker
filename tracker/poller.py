import time
import logging
from .hyperliquid import get_orders, get_positions
from .formatting import fmt_event
from .state import WalletState

log = logging.getLogger(__name__)


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

    log.info("Polling every %ds for %d wallet(s)…", interval, len(wallets))
    while True:
        time.sleep(interval)
        if heartbeat is not None:
            heartbeat[0] = time.time()
        for w in wallets:
            addr = w["address"]
            label = label_map.get(addr.lower(), addr[:8])
            try:
                positions = get_positions(addr)
                events = state.update(addr, positions)
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
