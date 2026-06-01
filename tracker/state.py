class WalletState:
    def __init__(self):
        self._state: dict[str, dict] = {}

    def seed(self, address: str, positions: dict):
        self._state[address.lower()] = positions

    def update(self, address: str, new_positions: dict) -> list[dict]:
        addr = address.lower()
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
        return self._state
