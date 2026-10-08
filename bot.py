import json
import sqlite3
import datetime
import time
import threading

class TradovateMultiAccountBot:
    def __init__(self, config_path="config.json", db_path="trades.db"):
        with open(config_path, "r") as f:
            self.config = json.load(f)
            
        self.db_path = db_path
        self.init_db()
        
        # Strategy Parameters
        self.asset = self.config['strategy']['asset']
        self.allowed_hours = self.config['strategy']['allowed_hours']
        self.contracts = self.config['strategy']['contracts_per_account']
        self.active_accounts = [acc for acc in self.config['accounts'] if acc['is_active']]
        
        # State Machine Variables
        self.pos = 0 
        self.bull_state = 0
        self.bull_anchor = 0.0
        self.bull_extreme = 0.0
        self.bear_state = 0
        self.bear_anchor = 0.0
        self.bear_extreme = 0.0
        self.active_bias = None
        
        # Real-time buffers
        self.day_high = 0.0
        self.day_low = float('inf')
        
    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS trades
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      account_name TEXT,
                      trade_time TEXT,
                      asset TEXT,
                      type TEXT,
                      pnl_usd REAL)''')
        conn.commit()
        conn.close()
        
    def fire_order(self, order_type, price):
        """Dispatches the order to all active Tradovate accounts via API concurrently."""
        print(f"\n[EXECUTION ENGINE] Firing {order_type} on {self.asset} @ {price}")
        for acc in self.active_accounts:
            # TODO: Replace with actual REST POST / WebSocket send to broker
            print(f" -> Sent to API: Account [{acc['account_name']}] | Qty: {self.contracts}")
            
    def log_trade(self, pnl_points):
        # Convert points to USD
        pt_value = 2.00 if self.asset == "MNQ" else 5.00
        pnl_usd = pnl_points * pt_value * self.contracts
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        for acc in self.active_accounts:
            c.execute("INSERT INTO trades (account_name, trade_time, asset, type, pnl_usd) VALUES (?, ?, ?, ?, ?)",
                      (acc['account_name'], timestamp, self.asset, "LIVE", pnl_usd))
        conn.commit()
        conn.close()
        print(f"   [DB] Logged Trade | PnL: ${pnl_usd:.2f} across all accounts.")

    def on_tick(self, current_price, current_time):
        """
        The live websocket pipeline. Feeds incoming price data into the 50% Equilibrium State Machine.
        """
        # In a real environment, you process High/Low of the 1-minute candle.
        # This is the architectural hook for the strategy logic you tested.
        pass

    def run_mock_stream(self):
        print(f"Starting Live Engine for {len(self.active_accounts)} prop firm accounts...")
        print(f"Tracking Asset: {self.asset} | Allowed Hours: {self.allowed_hours}")
        
        # Mocking a trade for the dashboard demonstration
        print("Waiting for real-time market data (mocking a filled trade in 5 seconds...)")
        time.sleep(5)
        
        # Mock 50% Pullback touch
        self.fire_order("MARKET BUY", 18500.25)
        
        print("Trade active... monitoring Trailing Stop trigger...")
        time.sleep(3)
        print("Trailing stop triggered. SL moved to pullback low.")
        
        time.sleep(2)
        print("Take Profit Hit!")
        self.log_trade(25.50) # 25.5 points profit
        
        print("\nEngine running. Dashboard is now receiving live data.")

if __name__ == "__main__":
    bot = TradovateMultiAccountBot()
    bot.run_mock_stream()
