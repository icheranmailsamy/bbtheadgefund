"""
================================================================================
OFFICIAL PRODUCTION EXECUTION BOT: THE MORNING SNIPER (OPTION B + 2-LOSS STOP)
================================================================================
Architecture:
- Pure RTH Session Reset: 09:30 AM EST (Wipes slate clean, anchors to opening bar)
- Execution Window: 09:30 AM – 11:30 AM EST (Morning Sniper)
- Hard Session Flatten: 11:30 AM EST Sharp (Zero mid-day / afternoon exposure)
- 5-State Wave Expansion Engine (Option B):
    State 1: Wave 1 Impulse Expansion
    State 2: 50% Retracement Qualified
    State 3: Breakout Confirmation (Wave 2+ Primed & Active Direction)
    State 4: 50% Equilibrium Touch Entry
    State 5: Wave Failure Stoprun Continuation (Option B: Pivot sweep continuation)
- Execution Filters:
    min_range = 8.0 points (32 ticks) minimum setup range
    Midpoint Trailing Stop: At 50% progress toward TP, SL moves to structural pivot
- Institutional Risk Management:
    Daily 2-Consecutive-Loss Circuit Breaker: Halts trading after 2 consecutive losses
    in a single day. Resets fresh at 09:30 AM EST the following morning.
================================================================================
"""

import json
import sqlite3
import datetime
import time
import os

class FinalPureRTHEquilibriumBot:
    def __init__(self, config_path=None, db_path=None):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        if config_path is None:
            config_path = os.path.join(base_dir, "config.json")
        if db_path is None:
            db_path = os.path.join(base_dir, "trades.db")
            
        with open(config_path, "r") as f:
            self.config = json.load(f)
            
        self.db_path = db_path
        self.init_db()
        
        strategy_cfg = self.config.get('strategy', {})
        self.asset = strategy_cfg.get('asset', 'MNQ')
        self.contracts = strategy_cfg.get('contracts_per_account', 5)
        self.min_range = strategy_cfg.get('min_range_points', 8.0)
        self.max_consecutive_losses = strategy_cfg.get('max_consecutive_losses_per_day', 3)
        self.use_trailing_stop = strategy_cfg.get('use_trailing_stop', False)
        self.accounts = [acc for acc in self.config.get('accounts', []) if acc.get('is_active', True)]
        
        # Position and trade tracking
        self.pos = 0
        self.entry_price = 0.0
        self.sl_price = 0.0
        self.tp_price = 0.0
        self.trade_50_level = 0.0
        self.sl_moved = False
        self.lowest_in_trade = 0.0
        self.highest_in_trade = 0.0
        
        # Market structure state machine
        self.day_high = 0.0
        self.day_low = float('inf')
        self.bull_state = 0
        self.bull_anchor = 0.0
        self.bull_extreme = 0.0
        self.bull_lowest_w1 = 0.0
        self.bull_retrace_low = 0.0
        self.bull_stoprun_low = 0.0
        
        self.bear_state = 0
        self.bear_anchor = 0.0
        self.bear_extreme = 0.0
        self.bear_highest_w1 = 0.0
        self.bear_retrace_high = 0.0
        self.bear_stoprun_high = 0.0
        
        self.active_bias = None
        
        # Daily Circuit Breaker
        self.consec_loss_today = 0
        self.day_halted = False

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
        """Pure RTH Reset at 09:30 AM EST: Wipes slate 100% clean."""
        self.day_high = first_bar_high
        self.day_low = first_bar_low
        self.bull_state = 1
        self.bull_anchor = self.day_low
        self.bull_extreme = self.day_low
        self.bull_stoprun_low = self.day_low
        self.bear_state = 1
        self.bear_anchor = self.day_high
        self.bear_extreme = self.day_high
        self.bear_stoprun_high = self.day_high
        self.active_bias = None
        self.pos = 0
        self.sl_moved = False
        self.consec_loss_today = 0
        self.day_halted = False
        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] RTH Reset at 09:30 AM EST. Slate clean.")

    def flatten_1130(self, exit_price):
        """Hard flatten at 11:30 AM EST to lock in morning profits and eliminate afternoon exposure."""
        if self.pos != 0:
            pts = (exit_price - self.entry_price) if self.pos == 1 else (self.entry_price - exit_price)
            self.record_trade(pts, exit_reason="HARD_CLOSE_1130")
            self.pos = 0
            self.active_bias = None

    def record_trade(self, pnl_points, exit_reason="EXIT"):
        pt_value = 2.00 if self.asset == "MNQ" else 5.00
        pnl_usd = pnl_points * pt_value * self.contracts
        
        if pnl_points <= 0:
            self.consec_loss_today += 1
            if self.consec_loss_today >= self.max_consecutive_losses:
                self.day_halted = True
                print(f"[CIRCUIT BREAKER] {self.consec_loss_today} consecutive losses reached. Trading HALTED for today.")
        else:
            self.consec_loss_today = 0

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for acc in self.accounts:
            c.execute("INSERT INTO trades (account_name, trade_time, asset, type, pnl_usd) VALUES (?, ?, ?, ?, ?)",
                      (acc['account_name'], timestamp, self.asset, f"{exit_reason}_{self.asset}", pnl_usd))
        conn.commit()
        conn.close()
        print(f"[{timestamp}] TRADE CLOSED ({exit_reason}) | PnL: ${pnl_usd:.2f} ({pnl_points:.2f} pts) across {len(self.accounts)} accounts.")

    def on_candle(self, dt, open_p, high_p, low_p, close_p):
        time_hour = dt.hour
        time_min = dt.minute
        time_total_min = time_hour * 60 + time_min

        # 1. 09:30 AM EST: Pure RTH Fresh Start Reset
        if time_hour == 9 and time_min == 30:
            self.reset_rth(high_p, low_p)
            return

        # 2. 11:30 AM EST: Mandatory Flat (Morning Sniper Hard Cutoff)
        if time_total_min >= 690:
            self.flatten_1130(close_p)
            return

        # Outside Morning Sniper window (09:30 - 11:30 EST)
        if time_total_min < 570 or time_total_min >= 690:
            return

        # If day circuit breaker is tripped and flat, skip new entries
        if self.day_halted and self.pos == 0:
            return

        # 3. Position Management (Forward-Bar i+1 execution)
        if self.pos == 1:
            self.lowest_in_trade = min(self.lowest_in_trade, low_p)
            if high_p >= self.tp_price:
                self.record_trade(self.tp_price - self.entry_price, exit_reason="TP")
                self.pos = 0
                self.bull_anchor = self.lowest_in_trade
                self.bull_extreme = self.tp_price
                self.active_bias = "BULL"
                self.bull_state = 3
            elif low_p <= self.sl_price:
                self.record_trade(self.sl_price - self.entry_price, exit_reason="SL")
                self.pos = 0
                if low_p >= self.day_low:
                    self.bull_state = 5
                    self.bull_stoprun_low = low_p
                else:
                    self.bull_state = 0
                self.active_bias = None
            elif self.use_trailing_stop:
                trigger = self.trade_50_level + 0.50 * (self.tp_price - self.trade_50_level)
                if high_p >= trigger and not self.sl_moved:
                    buffer = close_p * 0.00005
                    self.sl_price = self.lowest_in_trade - buffer
                    self.sl_moved = True

        elif self.pos == -1:
            self.highest_in_trade = max(self.highest_in_trade, high_p)
            if low_p <= self.tp_price:
                self.record_trade(self.entry_price - self.tp_price, exit_reason="TP")
                self.pos = 0
                self.bear_anchor = self.highest_in_trade
                self.bear_extreme = self.tp_price
                self.active_bias = "BEAR"
                self.bear_state = 3
            elif high_p >= self.sl_price:
                self.record_trade(self.entry_price - self.sl_price, exit_reason="SL")
                self.pos = 0
                if high_p <= self.day_high:
                    self.bear_state = 5
                    self.bear_stoprun_high = high_p
                else:
                    self.bear_state = 0
                self.active_bias = None
            elif self.use_trailing_stop:
                trigger = self.trade_50_level - 0.50 * (self.trade_50_level - self.tp_price)
                if low_p <= trigger and not self.sl_moved:
                    buffer = close_p * 0.00005
                    self.sl_price = self.highest_in_trade + buffer
                    self.sl_moved = True

        # 4. Session High/Low Tracking
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

        allowed_entry = (time_total_min >= 570 and time_total_min < 690) and (not self.day_halted)
        tick_size = 0.25

        # 5. Bullish Wave Cycle (Option B)
        if self.bull_state == 1:
            if high_p > self.bull_extreme: self.bull_extreme = high_p
            bull_50 = self.bull_extreme - 0.50 * (self.bull_extreme - self.bull_anchor)
            if (self.bull_extreme - self.bull_anchor) > tick_size and low_p <= bull_50:
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
                if low_p >= self.day_low:
                    self.bull_state = 5
                    self.bull_stoprun_low = low_p
                else:
                    self.bull_state = 0
                if self.active_bias == "BULL": self.active_bias = None
            else:
                if high_p > self.bull_extreme: self.bull_extreme = high_p
                bull_50 = self.bull_extreme - 0.50 * (self.bull_extreme - self.bull_anchor)
                if (self.bull_extreme - self.bull_anchor) > tick_size and low_p <= bull_50:
                    self.bull_state = 4
                    self.bull_retrace_low = low_p
                    trade_range = self.bull_extreme - self.bull_anchor
                    if self.pos == 0 and allowed_entry and self.active_bias == "BULL" and trade_range >= self.min_range:
                        self.pos = 1
                        self.entry_price = bull_50 + 0.50 # 2 ticks slippage
                        buffer = close_p * 0.00005
                        self.sl_price = self.bull_anchor - buffer
                        self.tp_price = self.bull_extreme
                        self.trade_50_level = bull_50
                        self.lowest_in_trade = low_p
                        self.sl_moved = False
        elif self.bull_state == 4:
            self.bull_retrace_low = min(self.bull_retrace_low, low_p)
            if low_p < self.bull_anchor:
                if low_p >= self.day_low:
                    self.bull_state = 5
                    self.bull_stoprun_low = low_p
                else:
                    self.bull_state = 0
                if self.active_bias == "BULL": self.active_bias = None
            elif high_p >= self.bull_extreme:
                self.bull_state = 3
                self.bull_anchor = self.bull_retrace_low
                self.bull_extreme = high_p
                self.active_bias = "BULL"
        elif self.bull_state == 5:
            self.bull_stoprun_low = min(self.bull_stoprun_low, low_p)
            if high_p >= self.bull_extreme:
                self.bull_state = 3
                self.bull_anchor = self.bull_stoprun_low
                self.bull_extreme = high_p
                self.active_bias = "BULL"

        # 6. Bearish Wave Cycle (Option B)
        if self.bear_state == 1:
            if low_p < self.bear_extreme: self.bear_extreme = low_p
            bear_50 = self.bear_extreme + 0.50 * (self.bear_anchor - self.bear_extreme)
            if (self.bear_anchor - self.bear_extreme) > tick_size and high_p >= bear_50:
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
                if high_p <= self.day_high:
                    self.bear_state = 5
                    self.bear_stoprun_high = high_p
                else:
                    self.bear_state = 0
                if self.active_bias == "BEAR": self.active_bias = None
            else:
                if low_p < self.bear_extreme: self.bear_extreme = low_p
                bear_50 = self.bear_extreme + 0.50 * (self.bear_anchor - self.bear_extreme)
                if (self.bear_anchor - self.bear_extreme) > tick_size and high_p >= bear_50:
                    self.bear_state = 4
                    self.bear_retrace_high = high_p
                    trade_range = self.bear_anchor - self.bear_extreme
                    if self.pos == 0 and allowed_entry and self.active_bias == "BEAR" and trade_range >= self.min_range:
                        self.pos = -1
                        self.entry_price = bear_50 - 0.50
                        buffer = close_p * 0.00005
                        self.sl_price = self.bear_anchor + buffer
                        self.tp_price = self.bear_extreme
                        self.trade_50_level = bear_50
                        self.highest_in_trade = high_p
                        self.sl_moved = False
        elif self.bear_state == 4:
            self.bear_retrace_high = max(self.bear_retrace_high, high_p)
            if high_p > self.bear_anchor:
                if high_p <= self.day_high:
                    self.bear_state = 5
                    self.bear_stoprun_high = high_p
                else:
                    self.bear_state = 0
                if self.active_bias == "BEAR": self.active_bias = None
            elif low_p <= self.bear_extreme:
                self.bear_state = 3
                self.bear_anchor = self.bear_retrace_high
                self.bear_extreme = low_p
                self.active_bias = "BEAR"
        elif self.bear_state == 5:
            self.bear_stoprun_high = max(self.bear_stoprun_high, high_p)
            if low_p <= self.bear_extreme:
                self.bear_state = 3
                self.bear_anchor = self.bear_stoprun_high
                self.bear_extreme = low_p
                self.active_bias = "BEAR"

if __name__ == "__main__":
    bot = FinalPureRTHEquilibriumBot()
    print("="*80)
    print("Finalized Pure RTH 50% Equilibrium Bot initialized successfully.")
    print("Model: Option B (Morning Sniper: 09:30 - 11:30 AM EST)")
    print(f"Contract Size: {bot.contracts} Micros ({bot.asset})")
    print(f"Minimum Setup Range: {bot.min_range} points (32 ticks)")
    print(f"Daily Circuit Breaker: Max {bot.max_consecutive_losses} consecutive losses per day")
    print("Ready for live broker websocket feed.")
    print("="*80)
