import json
import os
import threading
from datetime import datetime, timezone

HISTORY_FILE = "history.json"


def _load_history() -> list[dict]:
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE) as f:
            raw = json.load(f)
        for e in raw:
            e["ts"] = datetime.fromisoformat(e["ts"])
        return raw
    except Exception:
        return []


def _save_history(history: list[dict]):
    with open(HISTORY_FILE, "w") as f:
        json.dump([{**e, "ts": e["ts"].isoformat()} for e in history], f)


class WalletState:
    def __init__(self):
        self._state: dict[str, dict] = {}
        self._history: list[dict] = _load_history()
        self._lock = threading.Lock()

    def seed(self, address: str, positions: dict):
        with self._lock:
            self._state[address.lower()] = positions

    def update(self, address: str, new_positions: dict) -> list[dict]:
        addr = address.lower()
        with self._lock:
            old = self._state.get(addr, {})
            events = []

            for coin, new_pos in new_positions.items():
                if coin not in old:
                    events.append({"type": "OPEN", "coin": coin, "pos": new_pos})
                else:
                    old_pos = old[coin]
                    if old_pos["side"] != new_pos["side"]:
                        events.append({"type": "FLIP", "coin": coin, "pos": new_pos, "old": old_pos})
                    elif abs(new_pos["size"]) > abs(old_pos["size"]) * 1.01:
                        events.append({"type": "INCREASE", "coin": coin, "pos": new_pos, "old": old_pos})
                    elif abs(new_pos["size"]) < abs(old_pos["size"]) * 0.99:
                        events.append({"type": "DECREASE", "coin": coin, "pos": new_pos, "old": old_pos})

            for coin in old:
                if coin not in new_positions:
                    events.append({"type": "CLOSE", "coin": coin, "old": old[coin]})

            self._state[addr] = new_positions
        return events

    def get_all_positions(self) -> dict[str, dict]:
        with self._lock:
            return dict(self._state)

    def log_event(self, event: dict, label: str):
        entry = {
            "ts": datetime.now(timezone.utc),
            "coin": event["coin"],
            "type": event["type"],
            "label": label,
            "pnl": event.get("old", event.get("pos", {})).get("unrealized_pnl"),
        }
        with self._lock:
            self._history.append(entry)
            _save_history(self._history)

    def get_history(self, since: datetime) -> list[dict]:
        with self._lock:
            return [e for e in self._history if e["ts"] >= since]
