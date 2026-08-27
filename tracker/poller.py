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


def poll_loop(
    config: dict,
    state: WalletState,
    send_fn,
    heartbeat: list | None = None,
    last_poll: list | None = None,
    config_lock=None,
):
    interval = config.get("poll_interval_seconds", 10)

    def snapshot() -> tuple[list[dict], bool]:
        # Read config["wallets"]/config["network"] fresh each cycle (under lock)
        # so /add_wallet, /remove_wallet, and /set_network — which reassign
        # config entries rather than mutate in place — actually take effect on
        # the running loop instead of it working off stale captured values.
        if config_lock is not None:
            with config_lock:
                return list(config["wallets"]), config.get("network", "mainnet") == "testnet"
        return list(config["wallets"]), config.get("network", "mainnet") == "testnet"

    initial_wallets, testnet = snapshot()
    for w in initial_wallets:
        try:
            positions = get_positions(w["address"], testnet=testnet)
            state.seed(w["address"], positions)
            log.info("Seeded %s: %d open position(s)", w.get("label", w["address"]), len(positions))
        except Exception as e:
            log.warning("Failed to seed %s: %s", w["address"], e)

    last_summary_day = datetime.now(timezone.utc).date()
    liq_warned: set[str] = set()  # track coins already warned to avoid spam
    current_network = "testnet" if testnet else "mainnet"

    log.info("Polling every %ds for %d wallet(s) on %s…", interval, len(initial_wallets), current_network)
    while True:
        time.sleep(interval)
        if heartbeat is not None:
            heartbeat[0] = time.time()

        wallets, testnet = snapshot()
        label_map = {w["address"].lower(): w.get("label", w["address"][:8]) for w in wallets}

        network = "testnet" if testnet else "mainnet"
        if network != current_network:
            # Positions on the other network are a completely different data
            # set — reseed instead of diffing against the old network's
            # positions, which would otherwise fire a false OPEN/CLOSE for
            # every position just because the network switched.
            log.info("Network switched %s -> %s; reseeding positions", current_network, network)
            current_network = network
            liq_warned.clear()
            for w in wallets:
                try:
                    positions = get_positions(w["address"], testnet=testnet)
                    state.seed(w["address"], positions)
                except Exception as e:
                    log.warning("Failed to reseed %s after network switch: %s", w["address"], e)
            if last_poll is not None:
                last_poll[0] = time.time()
            continue

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
                positions = get_positions(addr, testnet=testnet)
                events = state.update(addr, positions)

                # Liquidation risk check — only for wallets with liq_alert: true
                if w.get("liq_alert", False):
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
                        orders = get_orders(addr, positions, testnet=testnet)
                    except Exception as e:
                        log.warning("Failed to fetch orders for %s: %s", addr, e)
                for ev in events:
                    coin_orders = orders.get(ev["coin"]) if ev["type"] == "OPEN" else None
                    send_fn(fmt_event(ev, label, coin_orders))
                    state.log_event(ev, label)
                    log.info("Event [%s] %s %s", ev["type"], label, ev["coin"])
            except Exception as e:
                log.warning("Error polling %s: %s", addr, e)

        if last_poll is not None:
            last_poll[0] = time.time()
