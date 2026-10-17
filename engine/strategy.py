class PureRTHEquilibriumStrategyEngine:
    """
    Core Strategy Engine implementing:
    - Pure RTH Fresh Slate (09:30 AM EST)
    - 4-State Cycle (Wave 1 Impulse -> Retracement -> Breakout -> Wave 2 Entry)
    - 50% Equilibrium Touch
    - Recency Override
    """
    INSTRUMENT_SPECS = {
        "MNQ": {"point_value": 2.00, "tick_size": 0.25, "tick_value": 0.50},
        "NQ":  {"point_value": 20.00, "tick_size": 0.25, "tick_value": 5.00},
        "MES": {"point_value": 5.00, "tick_size": 0.25, "tick_value": 1.25},
        "ES":  {"point_value": 50.00, "tick_size": 0.25, "tick_value": 12.50},
    }

    def __init__(self, asset="MNQ", slippage_ticks=2):
        self.asset = asset.upper()
        spec = self.INSTRUMENT_SPECS.get(self.asset, self.INSTRUMENT_SPECS["MNQ"])
        self.tick_size = spec["tick_size"]
        self.slippage_penalty = slippage_ticks * self.tick_size
        
        self.day_high = 0.0
        self.day_low = float('inf')
        
        self.bull_state = 0
        self.bull_anchor = 0.0
        self.bull_extreme = 0.0
        self.bull_lowest_w1 = 0.0
        self.bull_retrace_low = 0.0
        
        self.bear_state = 0
        self.bear_anchor = 0.0
        self.bear_extreme = 0.0
        self.bear_highest_w1 = 0.0
        self.bear_retrace_high = 0.0
        
        self.active_bias = None

    def reset_at_open(self, first_bar_high, first_bar_low):
        """Wipes the slate 100% clean at 09:30 AM EST."""
        self.day_high = first_bar_high
        self.day_low = first_bar_low
        self.bull_state = 1
        self.bull_anchor = self.day_low
        self.bull_extreme = self.day_low
        self.bull_retrace_low = self.day_low
        self.bear_state = 1
        self.bear_anchor = self.day_high
        self.bear_extreme = self.day_high
        self.bear_retrace_high = self.day_high
        self.active_bias = None

    def process_bar(self, high_p, low_p, close_p, is_entry_allowed):
        """
        Processes an incoming 1-minute candle.
        Returns signal:
          None or dict: {'side': 'BUY'/'SELL', 'entry_price': x, 'sl_price': x, 'tp_price': x, 'trade_50_level': x}
        """
        # Update session extremes
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

        min_range = 5.0  # 5.0 points = 20 ticks minimum setup range (trade gate only)
        signal = None

        # Bullish Wave Logic (Pure Market Structure)
        if self.bull_state == 1:
            if high_p > self.bull_extreme: self.bull_extreme = high_p
            bull_50 = self.bull_extreme - 0.50 * (self.bull_extreme - self.bull_anchor)
            if (self.bull_extreme - self.bull_anchor) > self.tick_size and low_p <= bull_50:
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
                self.active_bias = "BULL" # Recency Override
        elif self.bull_state == 3:
            # Wave 2+ Expansion Phase: tracking peak
            if low_p < self.bull_anchor:
                self.bull_state = 0
                if self.active_bias == "BULL": self.active_bias = None
            else:
                if high_p > self.bull_extreme: self.bull_extreme = high_p
                bull_50 = self.bull_extreme - 0.50 * (self.bull_extreme - self.bull_anchor)
                if (self.bull_extreme - self.bull_anchor) > self.tick_size and low_p <= bull_50:
                    self.bull_state = 4
                    self.bull_retrace_low = low_p
                    trade_range = self.bull_extreme - self.bull_anchor
                    # Trade Execution Gate: min_range strictly decides whether to place the order
                    if is_entry_allowed and self.active_bias == "BULL" and trade_range >= min_range:
                        buffer = close_p * 0.00005
                        signal = {
                            'side': 'BUY',
                            'entry_price': bull_50 + self.slippage_penalty,
                            'sl_price': self.bull_anchor - buffer,
                            'tp_price': self.bull_extreme,
                            'trade_50_level': bull_50,
                            'extreme_low': low_p
                        }
        elif self.bull_state == 4:
            # Wave 2+ Retracement Phase: tracking pullback low
            self.bull_retrace_low = min(self.bull_retrace_low, low_p)
            if low_p < self.bull_anchor:
                self.bull_state = 0
                if self.active_bias == "BULL": self.active_bias = None
            elif high_p >= self.bull_extreme:
                # Cycle Completed! Move and start measuring next wave regardless of trade
                self.bull_state = 3
                self.bull_anchor = self.bull_retrace_low
                self.bull_extreme = high_p
                self.active_bias = "BULL"

        # Bearish Wave Logic (Pure Market Structure)
        if self.bear_state == 1:
            if low_p < self.bear_extreme: self.bear_extreme = low_p
            bear_50 = self.bear_extreme + 0.50 * (self.bear_anchor - self.bear_extreme)
            if (self.bear_anchor - self.bear_extreme) > self.tick_size and high_p >= bear_50:
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
                self.active_bias = "BEAR" # Recency Override
        elif self.bear_state == 3:
            # Wave 2+ Expansion Phase: tracking valley
            if high_p > self.bear_anchor:
                self.bear_state = 0
                if self.active_bias == "BEAR": self.active_bias = None
            else:
                if low_p < self.bear_extreme: self.bear_extreme = low_p
                bear_50 = self.bear_extreme + 0.50 * (self.bear_anchor - self.bear_extreme)
                if (self.bear_anchor - self.bear_extreme) > self.tick_size and high_p >= bear_50:
                    self.bear_state = 4
                    self.bear_retrace_high = high_p
                    trade_range = self.bear_anchor - self.bear_extreme
                    # Trade Execution Gate: min_range strictly decides whether to place the order
                    if is_entry_allowed and self.active_bias == "BEAR" and trade_range >= min_range:
                        buffer = close_p * 0.00005
                        signal = {
                            'side': 'SELL',
                            'entry_price': bear_50 - self.slippage_penalty,
                            'sl_price': self.bear_anchor + buffer,
                            'tp_price': self.bear_extreme,
                            'trade_50_level': bear_50,
                            'extreme_high': high_p
                        }
        elif self.bear_state == 4:
            # Wave 2+ Retracement Phase: tracking pullback high
            self.bear_retrace_high = max(self.bear_retrace_high, high_p)
            if high_p > self.bear_anchor:
                self.bear_state = 0
                if self.active_bias == "BEAR": self.active_bias = None
            elif low_p <= self.bear_extreme:
                # Cycle Completed! Move and start measuring next wave regardless of trade
                self.bear_state = 3
                self.bear_anchor = self.bear_retrace_high
                self.bear_extreme = low_p
                self.active_bias = "BEAR"

        return signal

    def get_status(self):
        return {
            "active_bias": self.active_bias or "NEUTRAL",
            "bull_state": f"State {self.bull_state}",
            "bull_anchor": f"{self.bull_anchor:.2f}" if self.bull_anchor > 0 else "---",
            "bull_peak": f"{self.bull_extreme:.2f}" if self.bull_extreme > 0 else "---",
            "bear_state": f"State {self.bear_state}",
            "bear_anchor": f"{self.bear_anchor:.2f}" if self.bear_anchor > 0 else "---",
            "bear_peak": f"{self.bear_extreme:.2f}" if self.bear_extreme > 0 else "---",
        }
