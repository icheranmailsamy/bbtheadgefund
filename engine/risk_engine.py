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

    def __init__(self, asset="MNQ"):
        self.asset = asset.upper()
        spec = self.INSTRUMENT_SPECS.get(self.asset, self.INSTRUMENT_SPECS["MNQ"])
        self.pt_value = spec["point_value"]
        self.tick_size = spec["tick_size"]
        self.tick_value = spec["tick_value"]
        
        self.in_trade = False
        self.side = None
        self.entry_price = 0.0
        self.sl_price = 0.0
        self.tp_price = 0.0
        self.trade_50_level = 0.0
        self.sl_moved = False
        self.lowest_in_trade = 0.0
        self.highest_in_trade = 0.0

    def is_entry_allowed(self, dt):
        """09:30 to 15:50 EST allowed entries."""
        time_total_min = dt.hour * 60 + dt.minute
        return 570 <= time_total_min <= 950

    def is_eod_flatten_time(self, dt):
        """15:59 EST mandatory close."""
        return dt.hour == 15 and dt.minute >= 59

    def open_position(self, signal):
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
            both_hit = (low_p <= self.sl_price) and (high_p >= self.tp_price)

            if both_hit:
                # USER RULE: Single candle SL+TP is strictly a LOSS
                pts = self.sl_price - self.entry_price
                exit_event = {'exit_type': 'SL_AMBIGUOUS_BAR', 'exit_price': self.sl_price, 'pnl_points': pts}
                self.in_trade = False
            elif low_p <= self.sl_price:
                pts = self.sl_price - self.entry_price
                exit_event = {'exit_type': 'SL', 'exit_price': self.sl_price, 'pnl_points': pts}
                self.in_trade = False
            elif high_p >= self.tp_price:
                pts = self.tp_price - self.entry_price
                exit_event = {'exit_type': 'TP', 'exit_price': self.tp_price, 'pnl_points': pts}
                self.in_trade = False
            else:
                # Dynamic Trailing Stop Trigger
                trigger = self.trade_50_level + 0.50 * (self.tp_price - self.trade_50_level)
                if high_p >= trigger and not self.sl_moved:
                    buffer = close_p * 0.00005
                    self.sl_price = self.lowest_in_trade - buffer
                    self.sl_moved = True

        elif self.side == 'SELL':
            self.highest_in_trade = max(self.highest_in_trade, high_p)
            both_hit = (high_p >= self.sl_price) and (low_p <= self.tp_price)

            if both_hit:
                # USER RULE: Single candle SL+TP is strictly a LOSS
                pts = self.entry_price - self.sl_price
                exit_event = {'exit_type': 'SL_AMBIGUOUS_BAR', 'exit_price': self.sl_price, 'pnl_points': pts}
                self.in_trade = False
            elif high_p >= self.sl_price:
                pts = self.entry_price - self.sl_price
                exit_event = {'exit_type': 'SL', 'exit_price': self.sl_price, 'pnl_points': pts}
                self.in_trade = False
            elif low_p <= self.tp_price:
                pts = self.entry_price - self.tp_price
                exit_event = {'exit_type': 'TP', 'exit_price': self.tp_price, 'pnl_points': pts}
                self.in_trade = False
            else:
                trigger = self.trade_50_level - 0.50 * (self.trade_50_level - self.tp_price)
                if low_p <= trigger and not self.sl_moved:
                    buffer = close_p * 0.00005
                    self.sl_price = self.highest_in_trade + buffer
                    self.sl_moved = True

        return exit_event

    def force_eod_flatten(self, close_p):
        """Hard exit at 15:59."""
        if not self.in_trade:
            return None
        pts = (close_p - self.entry_price) if self.side == 'BUY' else (self.entry_price - close_p)
        exit_event = {'exit_type': 'EOD_FLATTEN', 'exit_price': close_p, 'pnl_points': pts}
        self.in_trade = False
        return exit_event
