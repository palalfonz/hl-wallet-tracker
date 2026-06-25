import requests

HL_API = "https://api.hyperliquid.xyz/info"

def get_positions(address: str) -> dict:
    resp = requests.post(
        HL_API,
        json={"type": "clearinghouseState", "user": address},
        timeout=10,
    )
    resp.raise_for_status()
    positions = {}
    for p in resp.json().get("assetPositions", []):
        pos = p.get("position", {})
        szi = float(pos.get("szi", 0))
        if szi == 0:
            continue
        coin = pos.get("coin", "?")
        position_value = float(pos.get("positionValue", 0))
        mark_px = position_value / abs(szi) if szi else 0
        positions[coin] = {
            "size": szi,
            "side": "LONG" if szi > 0 else "SHORT",
            "entry_px": float(pos.get("entryPx", 0)),
            "mark_px": mark_px,
            "unrealized_pnl": float(pos.get("unrealizedPnl", 0)),
            "leverage": pos.get("leverage", {}).get("value", "?"),
            "position_value": position_value,
        }
    return positions


_TP_TYPES = {"Take Profit Market", "Take Profit Limit"}
_SL_TYPES = {"Stop Market", "Stop Limit"}


def get_orders(address: str, positions: dict | None = None) -> dict:
    """Returns {coin: {"tp": [price, ...], "sl": price | None}}

    Uses frontendOpenOrders which includes trigger orders (position TP/SL).
    Trigger orders use triggerPx as the relevant price, not limitPx.
    """
    resp = requests.post(
        HL_API,
        json={"type": "frontendOpenOrders", "user": address},
        timeout=10,
    )
    resp.raise_for_status()
    result: dict[str, dict] = {}
    for order in resp.json():
        if not order.get("isPositionTpsl"):
            continue
        coin = order.get("coin", "?")
        order_type = order.get("orderType", "")
        price = float(order.get("triggerPx") or order.get("limitPx", 0))
        entry = result.setdefault(coin, {"tp": [], "sl": None})
        if order_type in _TP_TYPES:
            entry["tp"].append(price)
        elif order_type in _SL_TYPES:
            entry["sl"] = price
    for coin in result:
        result[coin]["tp"].sort()
    return result
