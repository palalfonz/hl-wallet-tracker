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
        }
    return positions
