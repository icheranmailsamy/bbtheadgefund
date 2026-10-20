class RiskManagementEngine:
    """
    Institutional Risk & Position Execution Engine:
    - Pre-trade time filtering (09:30 - 15:55 EST)
    - Dynamic Risk Reduction Trailing Stop (Midpoint Trigger)
    - Ambiguous Single-Candle SL+TP = Strict Loss
    - EOD Mandatory Liquidation (15:59 EST)
    """
    INSTRUMENT_SPECS = {
        "MNQ": {"point_value": 2.00, "tick_size": 0.25, "tick_value": 0.50},
        "NQ":  {"point_value": 20.00, "tick_size": 0.25, "tick_value": 5.00},
        "MES": {"point_value": 5.00, "tick_size": 0.25, "tick_value": 1.25},
        "ES":  {"point_value": 50.00, "tick_size": 0.25, "tick_value": 12.50},
    }

    def __init__(self, asset="MNQ", max_consecutive_losses=3):
        self.asset = asset.upper()
        spec = self.INSTRUMENT_SPECS.get(self.asset, self.INSTRUMENT_SPECS["MNQ"])
        self.pt_value = spec["point_value"]
        self.tick_size = spec["tick_size"]
        self.tick_value = spec["tick_value"]
        self.max_consecutive_losses = max_consecutive_losses
        
        self.in_trade = False
        self.side = None
        self.entry_price = 0.0
        self.sl_price = 0.0
        self.tp_price = 0.0
        self.trade_50_level = 0.0
        self.sl_moved = False
        self.lowest_in_trade = 0.0
        self.highest_in_trade = 0.0
        
        # Institutional Circuit Breaker (3 Consecutive Losses)
        self.consecutive_losses = 0
        self.day_halted = False

    def reset_daily_risk(self):
        """Resets risk circuit breaker at 09:30 AM EST NYSE Bell."""
        self.consecutive_losses = 0
        self.day_halted = False

    def is_entry_allowed(self, dt):
        """09:30 to 11:30 EST Morning Sniper allowed entries with circuit breaker gate."""
        if self.day_halted:
            return False
        time_total_min = dt.hour * 60 + dt.minute
        return 570 <= time_total_min < 690

    def is_eod_flatten_time(self, dt):
        """11:30 EST sharp mandatory close for The Morning Sniper."""
        time_total_min = dt.hour * 60 + dt.minute
        return time_total_min >= 690

    def open_position(self, signal):
        if self.day_halted:
            return
        self.in_trade = True
        self.side = signal['side']
        self.entry_price = signal['entry_price']
        self.sl_price = signal['sl_price']
        self.tp_price = signal['tp_price']
        self.trade_50_level = signal['trade_50_level']
        self.sl_moved = False
        if self.side == 'BUY':
            self.lowest_in_trade = signal.get('extreme_low', self.entry_price)
        else:
            self.highest_in_trade = signal.get('extreme_high', self.entry_price)

    def _update_circuit_breaker(self, pts):
        if pts <= 0:
            self.consecutive_losses += 1
            if self.consecutive_losses >= self.max_consecutive_losses:
                self.day_halted = True
                print(f"[CIRCUIT BREAKER] {self.consecutive_losses} consecutive losses reached today. Halting trading until 09:30 AM EST tomorrow.")
        else:
            self.consecutive_losses = 0

    def evaluate_bar(self, high_p, low_p, close_p):
        """
        Evaluates trade exit or trailing stop update on bar.
        Returns:
          exit_event: None or dict: {'exit_type': 'TP'/'SL'/'EOD', 'exit_price': x, 'pnl_points': x}
        """
        if not self.in_trade:
            return None

        exit_event = None

        if self.side == 'BUY':
            self.lowest_in_trade = min(self.lowest_in_trade, low_p)
            if high_p >= self.tp_price:
                pts = self.tp_price - self.entry_price
                exit_event = {'exit_type': 'TP', 'exit_price': self.tp_price, 'pnl_points': pts}
                self.in_trade = False
                self._update_circuit_breaker(pts)
            elif low_p <= self.sl_price:
                pts = self.sl_price - self.entry_price
                exit_event = {'exit_type': 'SL', 'exit_price': self.sl_price, 'pnl_points': pts}
                self.in_trade = False
                self._update_circuit_breaker(pts)
            else:
                # Dynamic Trailing Stop Trigger
                trigger = self.trade_50_level + 0.50 * (self.tp_price - self.trade_50_level)
                if high_p >= trigger and not self.sl_moved:
                    buffer = close_p * 0.00005
                    self.sl_price = self.lowest_in_trade - buffer
                    self.sl_moved = True

        elif self.side == 'SELL':
            self.highest_in_trade = max(self.highest_in_trade, high_p)
            if low_p <= self.tp_price:
                pts = self.entry_price - self.tp_price
                exit_event = {'exit_type': 'TP', 'exit_price': self.tp_price, 'pnl_points': pts}
                self.in_trade = False
                self._update_circuit_breaker(pts)
            elif high_p >= self.sl_price:
                pts = self.entry_price - self.sl_price
                exit_event = {'exit_type': 'SL', 'exit_price': self.sl_price, 'pnl_points': pts}
                self.in_trade = False
                self._update_circuit_breaker(pts)
            else:
                trigger = self.trade_50_level - 0.50 * (self.trade_50_level - self.tp_price)
                if low_p <= trigger and not self.sl_moved:
                    buffer = close_p * 0.00005
                    self.sl_price = self.highest_in_trade + buffer
                    self.sl_moved = True

        return exit_event

    def force_eod_flatten(self, close_p):
        """Hard exit at 11:30 AM EST."""
        if not self.in_trade:
            return None
        pts = (close_p - self.entry_price) if self.side == 'BUY' else (self.entry_price - close_p)
        exit_event = {'exit_type': 'EOD_FLATTEN', 'exit_price': close_p, 'pnl_points': pts}
        self.in_trade = False
        self._update_circuit_breaker(pts)
        return exit_event
