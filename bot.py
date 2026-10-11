import json
import sqlite3
import datetime
import time

class FinalPureRTHEquilibriumBot:
    """
    FINAL PRODUCTION SPECIFICATION:
    - Asset: MNQ (Micro Nasdaq) or MES (Micro S&P 500)
    - Session: Pure RTH Day Session (09:30 - 15:55 EST)
    - Overnight Holding: STRICT ZERO (100% flat at 15:59 EST)
    - Anchor Reset: Pure RTH Fresh Start at 09:30 AM EST (zero overnight distortion)
    - Entry Trigger: Exact 50% Equilibrium Retracement (Market Order)
    - Stop Loss: Anchor (+ buffer)
    - Take Profit: Peak
    - Dynamic Trailing Stop: At 50% distance to target, SL moves to Pullback Extreme
    - Ambiguity Rule: Any single candle hitting both SL and TP is treated as a LOSS
    """
    def __init__(self, config_path="config.json", db_path="trades.db"):
        with open(config_path, "r") as f:
            self.config = json.load(f)
            
        self.db_path = db_path
        self.init_db()
        
        self.asset = self.config.get('strategy', {}).get('asset', 'MNQ')
        self.contracts = self.config.get('strategy', {}).get('contracts_per_account', 3)
        self.accounts = [acc for acc in self.config.get('accounts', []) if acc.get('is_active', True)]
        
        # State machine
        self.pos = 0
        self.entry_price = 0.0
        self.sl_price = 0.0
        self.tp_price = 0.0
        self.trade_50_level = 0.0
        self.sl_moved = False
        self.lowest_in_trade = 0.0
        self.highest_in_trade = 0.0
        
        self.day_high = 0.0
        self.day_low = float('inf')
        self.bull_state = 0
        self.bull_anchor = 0.0
        self.bull_extreme = 0.0
        self.bull_lowest_w1 = 0.0
        
        self.bear_state = 0
        self.bear_anchor = 0.0
        self.bear_extreme = 0.0
        self.bear_highest_w1 = 0.0
        
        self.active_bias = None

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

    def reset_rth(self, first_bar_high, first_bar_low):
        """Pure RTH Reset at 09:30 AM EST: Wipes the slate 100% clean."""
        self.day_high = first_bar_high
        self.day_low = first_bar_low
        self.bull_state = 1
        self.bull_anchor = self.day_low
        self.bull_extreme = self.day_low
        self.bear_state = 1
        self.bear_anchor = self.day_high
        self.bear_extreme = self.day_high
        self.active_bias = None
        self.pos = 0

    def flatten_eod(self, exit_price):
        """Hard flatten at 15:59 EST to eliminate overnight risk."""
        if self.pos != 0:
            pts = (exit_price - self.entry_price) if self.pos == 1 else (self.entry_price - exit_price)
            self.log_trade(pts)
            self.pos = 0
            self.active_bias = None

    def log_trade(self, pnl_points):
        pt_value = 2.00 if self.asset == "MNQ" else 5.00
        pnl_usd = pnl_points * pt_value * self.contracts
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for acc in self.accounts:
            c.execute("INSERT INTO trades (account_name, trade_time, asset, type, pnl_usd) VALUES (?, ?, ?, ?, ?)",
                      (acc['account_name'], timestamp, self.asset, "LIVE_RTH", pnl_usd))
        conn.commit()
        conn.close()
        print(f"[{timestamp}] TRADE CLOSED | PnL: ${pnl_usd:.2f} across {len(self.accounts)} accounts.")

    def on_candle(self, dt, open_p, high_p, low_p, close_p):
        time_hour = dt.hour
        time_min = dt.minute
        time_total_min = time_hour * 60 + time_min

        # 09:30 AM EST: Pure RTH Fresh Start
        if time_hour == 9 and time_min == 30:
            self.reset_rth(high_p, low_p)
            return

        # 15:59 EST: Mandatory Flat (Zero Overnight)
        if time_hour == 15 and time_min >= 59:
            self.flatten_eod(close_p)
            return

        # Outside RTH: Skip
        if time_total_min < 570 or time_total_min >= 960:
            return

        # Update Session Extremes
        if low_p < self.day_low:
            self.day_low = low_p
            self.bull_state = 1
            self.bull_anchor = self.day_low
            self.bull_extreme = self.day_low
            if self.active_bias == "BULL": self.active_bias = None

        if high_p > self.day_high:
            self.day_high = high_p
            self.bear_state = 1
            self.bear_anchor = self.day_high
            self.bear_extreme = self.day_high
            if self.active_bias == "BEAR": self.active_bias = None

        min_range = close_p * 0.0004
        allowed_entry = (time_total_min >= 570 and time_total_min <= 950)
        entered = False

        # Bullish State Machine
        if self.bull_state == 1:
            if high_p > self.bull_extreme: self.bull_extreme = high_p
            bull_50 = self.bull_extreme - 0.50 * (self.bull_extreme - self.bull_anchor)
            if (self.bull_extreme - self.bull_anchor) >= min_range and low_p <= bull_50:
                self.bull_state = 2
                self.bull_lowest_w1 = low_p
        elif self.bull_state == 2:
            self.bull_lowest_w1 = min(self.bull_lowest_w1, low_p)
            if low_p < self.bull_anchor:
                self.bull_state = 0
                if self.active_bias == "BULL": self.active_bias = None
            elif high_p >= self.bull_extreme:
                self.bull_state = 3
                self.bull_anchor = self.bull_lowest_w1
                self.bull_extreme = high_p
                self.active_bias = "BULL"
        elif self.bull_state == 3:
            if low_p < self.bull_anchor:
                self.bull_state = 0
                if self.active_bias == "BULL": self.active_bias = None
            else:
                if high_p > self.bull_extreme: self.bull_extreme = high_p
                bull_50 = self.bull_extreme - 0.50 * (self.bull_extreme - self.bull_anchor)
                if self.pos == 0 and allowed_entry and self.active_bias == "BULL" and (self.bull_extreme - self.bull_anchor) >= min_range and low_p <= bull_50:
                    self.pos = 1
                    self.entry_price = bull_50 + 0.50 # 2 ticks slippage
                    buffer = close_p * 0.00005
                    self.sl_price = self.bull_anchor - buffer
                    self.tp_price = self.bull_extreme
                    self.trade_50_level = bull_50
                    self.lowest_in_trade = low_p
                    self.sl_moved = False
                    entered = True

        # Bearish State Machine
        if self.bear_state == 1:
            if low_p < self.bear_extreme: self.bear_extreme = low_p
            bear_50 = self.bear_extreme + 0.50 * (self.bear_anchor - self.bear_extreme)
            if (self.bear_anchor - self.bear_extreme) >= min_range and high_p >= bear_50:
                self.bear_state = 2
                self.bear_highest_w1 = high_p
        elif self.bear_state == 2:
            self.bear_highest_w1 = max(self.bear_highest_w1, high_p)
            if high_p > self.bear_anchor:
                self.bear_state = 0
                if self.active_bias == "BEAR": self.active_bias = None
            elif low_p <= self.bear_extreme:
                self.bear_state = 3
                self.bear_anchor = self.bear_highest_w1
                self.bear_extreme = low_p
                self.active_bias = "BEAR"
        elif self.bear_state == 3:
            if high_p > self.bear_anchor:
                self.bear_state = 0
                if self.active_bias == "BEAR": self.active_bias = None
            else:
                if low_p < self.bear_extreme: self.bear_extreme = low_p
                bear_50 = self.bear_extreme + 0.50 * (self.bear_anchor - self.bear_extreme)
                if self.pos == 0 and not entered and allowed_entry and self.active_bias == "BEAR" and (self.bear_anchor - self.bear_extreme) >= min_range and high_p >= bear_50:
                    self.pos = -1
                    self.entry_price = bear_50 - 0.50
                    buffer = close_p * 0.00005
                    self.sl_price = self.bear_anchor + buffer
                    self.tp_price = self.bear_extreme
                    self.trade_50_level = bear_50
                    self.highest_in_trade = high_p
                    self.sl_moved = False
                    entered = True

        # Position Management
        if self.pos == 1:
            self.lowest_in_trade = min(self.lowest_in_trade, low_p)
            both_hit = (low_p <= self.sl_price) and (high_p >= self.tp_price)
            if both_hit:
                self.log_trade(self.sl_price - self.entry_price)
                self.pos = 0; self.bull_state = 0; self.active_bias = None
            elif low_p <= self.sl_price:
                self.log_trade(self.sl_price - self.entry_price)
                self.pos = 0; self.bull_state = 0; self.active_bias = None
            elif high_p >= self.tp_price:
                self.log_trade(self.tp_price - self.entry_price)
                self.pos = 0
                self.bull_anchor = self.lowest_in_trade
                self.bull_extreme = self.tp_price
                self.active_bias = "BULL"
            else:
                trigger = self.trade_50_level + 0.50 * (self.tp_price - self.trade_50_level)
                if high_p >= trigger and not self.sl_moved:
                    buffer = close_p * 0.00005
                    self.sl_price = self.lowest_in_trade - buffer
                    self.sl_moved = True

        elif self.pos == -1:
            self.highest_in_trade = max(self.highest_in_trade, high_p)
            both_hit = (high_p >= self.sl_price) and (low_p <= self.tp_price)
            if both_hit:
                self.log_trade(self.entry_price - self.sl_price)
                self.pos = 0; self.bear_state = 0; self.active_bias = None
            elif high_p >= self.sl_price:
                self.log_trade(self.entry_price - self.sl_price)
                self.pos = 0; self.bear_state = 0; self.active_bias = None
            elif low_p <= self.tp_price:
                self.log_trade(self.entry_price - self.tp_price)
                self.pos = 0
                self.bear_anchor = self.highest_in_trade
                self.bear_extreme = self.tp_price
                self.active_bias = "BEAR"
            else:
                trigger = self.trade_50_level - 0.50 * (self.trade_50_level - self.tp_price)
                if low_p <= trigger and not self.sl_moved:
                    buffer = close_p * 0.00005
                    self.sl_price = self.highest_in_trade + buffer
                    self.sl_moved = True

if __name__ == "__main__":
    bot = FinalPureRTHEquilibriumBot()
    print("Finalized Pure RTH 50% Equilibrium Bot initialized successfully.")
    print("Ready for live broker websocket feed.")
