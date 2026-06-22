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
        positions[coin] = {
            "size": szi,
            "side": "LONG" if szi > 0 else "SHORT",
            "entry_px": float(pos.get("entryPx", 0)),
            "unrealized_pnl": float(pos.get("unrealizedPnl", 0)),
            "leverage": pos.get("leverage", {}).get("value", "?"),
            "position_value": float(pos.get("positionValue", 0)),
        }
    return positions


def get_orders(address: str, positions: dict | None = None) -> dict:
    """Returns {coin: {"tp": [price, ...], "sl": price | None}}

    Hyperliquid doesn't return an orderType field, so we classify by
    comparing the order price to the position entry price:
    - reduce-only order above entry on a LONG = TP
    - reduce-only order below entry on a LONG = SL
    - reduce-only order below entry on a SHORT = TP
    - reduce-only order above entry on a SHORT = SL
    """
    resp = requests.post(
        HL_API,
        json={"type": "openOrders", "user": address},
        timeout=10,
    )
    resp.raise_for_status()
    result: dict[str, dict] = {}
    for order in resp.json():
        if not order.get("reduceOnly"):
            continue
        coin = order.get("coin", "?")
        price = float(order.get("limitPx", 0))
        entry = result.setdefault(coin, {"tp": [], "sl": None})
        pos = (positions or {}).get(coin, {})
        pos_side = pos.get("side", "LONG")
        entry_px = pos.get("entry_px", 0)
        is_tp = (pos_side == "LONG" and price > entry_px) or (pos_side == "SHORT" and price < entry_px)
        if is_tp:
            entry["tp"].append(price)
        else:
            entry["sl"] = price
    for coin in result:
        result[coin]["tp"].sort()
    return result
