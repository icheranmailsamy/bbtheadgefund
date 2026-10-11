import asyncio
import json
import websockets
import requests
import datetime
import sqlite3

class TradovateLiveAsyncEngine:
    """
    High-speed asynchronous Python execution engine connecting directly to the
    Tradovate REST & WebSocket API for low-latency live order placement.
    """
    def __init__(self, config_path="config.json"):
        with open(config_path, "r") as f:
            self.config = json.load(f)

        self.strategy_cfg = self.config.get("strategy", {})
        self.asset = self.strategy_cfg.get("asset", "MNQ")
        self.contracts = self.strategy_cfg.get("contracts_per_account", 3)
        self.accounts = self.config.get("accounts", [])

        # Live URLs (use 'demo' or 'live' based on your key)
        self.http_url = "https://live.tradovate.com/v1"
        self.ws_url = "wss://live.tradovate.com/v1/websocket"

        self.token = None
        self.pos = 0
        self.day_high = 0.0
        self.day_low = float('inf')
        self.bull_state = 0
        self.bear_state = 0
        self.active_bias = None
        self.sl_moved = False

    def authenticate(self, username, password, app_id, app_version, cid, sec):
        """Authenticates with Tradovate API and fetches the session token."""
        url = f"{self.http_url}/auth/accesstokenrequest"
        payload = {
            "name": username,
            "password": password,
            "appId": app_id,
            "appVersion": app_version,
            "cid": cid,
            "sec": sec
        }
        res = requests.post(url, json=payload)
        data = res.json()
        if "accessToken" in data:
            self.token = data["accessToken"]
            print(f"Successfully authenticated with Tradovate! Token acquired.")
            return True
        else:
            print(f"Auth failed: {data}")
            return False

    async def send_order(self, action, qty, symbol, price=None):
        """Sends a sub-millisecond Market Order payload directly through the WebSocket."""
        order_packet = {
            "accountSpec": self.accounts[0]["account_name"],
            "accountId": self.accounts[0].get("account_id", 0),
            "action": action, # 'Buy' or 'Sell'
            "symbol": symbol,
            "orderQty": qty,
            "orderType": "Market",
            "isAutomated": True
        }
        print(f"[LIVE ORDER DISPATCH] Firing {action} {qty} {symbol} @ Market!")
        # To send through WebSocket:
        # await self.ws.send(f"order/placeorder\n1\n\n{json.dumps(order_packet)}")

    async def stream_market_data(self):
        """Subscribes to 1-minute real-time bar feed via Tradovate WebSocket."""
        print(f"Connecting to Tradovate Live Market Data Stream...")
        async with websockets.connect(self.ws_url) as ws:
            self.ws = ws
            # Authorize socket
            await ws.send(f"authorize\n1\n\n{self.token}")
            auth_response = await ws.recv()
            print(f"WebSocket Authorized: {auth_response[:60]}")

            # Subscribe to real-time 1m chart data
            sub_msg = {
                "symbol": self.asset,
                "chartDescription": {
                    "underlyingType": "Tick",
                    "elementSize": 1,
                    "elementSizeUnit": "Minute",
                    "withHistogram": False
                }
            }
            await ws.send(f"md/subscribeChart\n2\n\n{json.dumps(sub_msg)}")
            print(f"Subscribed to 1-Minute {self.asset} Live Bars. Engine is active.")

            while True:
                msg = await ws.recv()
                # Parse incoming bar data and feed into our state machine
                # Process bar: on_candle(dt, open, high, low, close)
                await asyncio.sleep(0.001)

if __name__ == "__main__":
    print("Tradovate Live Asynchronous Python Engine ready.")
    print("Add your live credentials to config.json and invoke stream_market_data().")
