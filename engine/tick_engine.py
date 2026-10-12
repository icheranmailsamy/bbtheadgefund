import datetime
from .strategy import PureRTHEquilibriumStrategyEngine
from .risk_engine import RiskManagementEngine
from .broker_router import BrokerMultiAccountRouter

class RealtimeTickAggregatorEngine:
    """
    Institutional Real-Time Tick Aggregator & Intra-Bar Signal Engine:
    - Ingests raw CME trade ticks (timestamp, price, volume)
    - Builds real-time 1-minute candlesticks (OHLCV)
    - Evaluates 50% Equilibrium Touch on EVERY TICK (intra-bar instant fill)
    - Evaluates Take Profit, Stop Loss, and Trailing Stops on EVERY TICK
    - Enforces 09:30 AM Fresh Slate and 15:59 EST Hard Flatten
    """
    def __init__(self, asset="MNQ", strategy=None, risk=None, router=None):
        self.asset = asset
        self.strategy = strategy or PureRTHEquilibriumStrategyEngine(asset=asset)
        self.risk = risk or RiskManagementEngine(asset=asset)
        self.router = router or BrokerMultiAccountRouter(asset=asset)
        
        self.current_bar_dt = None
        self.current_bar = None
        self.tick_count = 0
        self.last_tick_price = 0.0
        self.last_tick_time = None
        self.has_reset_today = False
        
    def reset_daily_slate(self, open_price):
        """Wipes the slate 100% clean at 09:30 AM NYSE Opening Bell."""
        self.strategy.reset_at_open(open_price, open_price)
        self.has_reset_today = True

    def on_tick(self, dt, price, volume=1):
        """
        Processes every individual tick streamed from the CME order book.
        Evaluates signals and risk in sub-millisecond real time.
        """
        self.tick_count += 1
        self.last_tick_price = price
        self.last_tick_time = dt

        # 1. 09:30 AM EST NYSE Opening Bell Fresh Slate Anchor
        is_rth_start = (dt.hour == 9 and dt.minute == 30)
        if is_rth_start and not self.has_reset_today:
            self.reset_daily_slate(price)

        # 2. Hard Flatten at 15:59 EST (Zero Overnight Holding)
        if self.risk.is_eod_flatten_time(dt):
            if self.risk.in_trade:
                exit_ev = self.risk.force_eod_flatten(price)
                if exit_ev:
                    self.router.dispatch_exit(exit_ev, self.risk.side, self.risk.entry_price)
            return None

        # 3. Active 1-Minute Candlestick Aggregator
        bar_minute = dt.replace(second=0, microsecond=0)
        
        if self.current_bar_dt is None:
            self.current_bar_dt = bar_minute
            self.current_bar = {
                'time': bar_minute,
                'open': price,
                'high': price,
                'low': price,
                'close': price,
                'volume': volume
            }
        elif bar_minute > self.current_bar_dt:
            # Previous 1-minute candle finalized! Pass to strategy for fractal update
            if self.current_bar is not None:
                self.strategy.process_bar(
                    high_p=self.current_bar['high'],
                    low_p=self.current_bar['low'],
                    close_p=self.current_bar['close'],
                    is_entry_allowed=False
                )
            # Start new active 1-minute candle
            self.current_bar_dt = bar_minute
            self.current_bar = {
                'time': bar_minute,
                'open': price,
                'high': price,
                'low': price,
                'close': price,
                'volume': volume
            }
        else:
            # Update in-progress 1-minute candle
            self.current_bar['high'] = max(self.current_bar['high'], price)
            self.current_bar['low'] = min(self.current_bar['low'], price)
            self.current_bar['close'] = price
            self.current_bar['volume'] += volume

        # 4. Intra-Bar Tick-Level Risk Evaluation (If In Position)
        if self.risk.in_trade:
            if self.risk.side == 'BUY':
                self.risk.lowest_in_trade = min(self.risk.lowest_in_trade, price)
                
                # Check Take Profit
                if price >= self.risk.tp_price:
                    exit_ev = {
                        'exit_type': 'TP_TICK',
                        'exit_price': self.risk.tp_price,
                        'pnl_points': self.risk.tp_price - self.risk.entry_price
                    }
                    self.risk.in_trade = False
                    self.router.dispatch_exit(exit_ev, 'BUY', self.risk.entry_price)
                    return {'type': 'EXIT', 'event': exit_ev}
                    
                # Check Stop Loss
                elif price <= self.risk.sl_price:
                    exit_ev = {
                        'exit_type': 'SL_TICK',
                        'exit_price': self.risk.sl_price,
                        'pnl_points': self.risk.sl_price - self.risk.entry_price
                    }
                    self.risk.in_trade = False
                    self.router.dispatch_exit(exit_ev, 'BUY', self.risk.entry_price)
                    return {'type': 'EXIT', 'event': exit_ev}
                    
                # Check Midpoint Trailing SL Trigger
                else:
                    mid_trigger = self.risk.trade_50_level + 0.50 * (self.risk.tp_price - self.risk.trade_50_level)
                    if price >= mid_trigger and not self.risk.sl_moved:
                        buffer = price * 0.00005
                        self.risk.sl_price = self.risk.lowest_in_trade - buffer
                        self.risk.sl_moved = True

            elif self.risk.side == 'SELL':
                self.risk.highest_in_trade = max(self.risk.highest_in_trade, price)
                
                # Check Take Profit
                if price <= self.risk.tp_price:
                    exit_ev = {
                        'exit_type': 'TP_TICK',
                        'exit_price': self.risk.tp_price,
                        'pnl_points': self.risk.entry_price - self.risk.tp_price
                    }
                    self.risk.in_trade = False
                    self.router.dispatch_exit(exit_ev, 'SELL', self.risk.entry_price)
                    return {'type': 'EXIT', 'event': exit_ev}
                    
                # Check Stop Loss
                elif price >= self.risk.sl_price:
                    exit_ev = {
                        'exit_type': 'SL_TICK',
                        'exit_price': self.risk.sl_price,
                        'pnl_points': self.risk.entry_price - self.risk.sl_price
                    }
                    self.risk.in_trade = False
                    self.router.dispatch_exit(exit_ev, 'SELL', self.risk.entry_price)
                    return {'type': 'EXIT', 'event': exit_ev}
                    
                # Check Midpoint Trailing SL Trigger
                else:
                    mid_trigger = self.risk.trade_50_level - 0.50 * (self.risk.trade_50_level - self.risk.tp_price)
                    if price <= mid_trigger and not self.risk.sl_moved:
                        buffer = price * 0.00005
                        self.risk.sl_price = self.risk.highest_in_trade + buffer
                        self.risk.sl_moved = True

            return None

        # 5. Intra-Bar Tick-Level 50% Touch Evaluation (If Flat)
        is_allowed = self.risk.is_entry_allowed(dt)
        if not is_allowed:
            return None

        min_range = price * 0.0004

        # Bullish Wave State 3: Check immediate tick touch of 50% Equilibrium
        if self.strategy.bull_state == 3 and self.strategy.active_bias == "BULL":
            if (self.strategy.bull_extreme - self.strategy.bull_anchor) >= min_range:
                bull_50 = self.strategy.bull_extreme - 0.50 * (self.strategy.bull_extreme - self.strategy.bull_anchor)
                if price <= bull_50:
                    buffer = price * 0.00005
                    signal = {
                        'side': 'BUY',
                        'entry_price': bull_50 + self.strategy.slippage_penalty,
                        'sl_price': self.strategy.bull_anchor - buffer,
                        'tp_price': self.strategy.bull_extreme,
                        'trade_50_level': bull_50,
                        'extreme_low': price,
                        'trigger_tick_time': dt.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    self.risk.open_position(signal)
                    self.router.dispatch_entry(signal)
                    return {'type': 'ENTRY', 'signal': signal}

        # Bearish Wave State 3: Check immediate tick touch of 50% Equilibrium
        if self.strategy.bear_state == 3 and self.strategy.active_bias == "BEAR":
            if (self.strategy.bear_anchor - self.strategy.bear_extreme) >= min_range:
                bear_50 = self.strategy.bear_extreme + 0.50 * (self.strategy.bear_anchor - self.strategy.bear_extreme)
                if price >= bear_50:
                    buffer = price * 0.00005
                    signal = {
                        'side': 'SELL',
                        'entry_price': bear_50 - self.strategy.slippage_penalty,
                        'sl_price': self.strategy.bear_anchor + buffer,
                        'tp_price': self.strategy.bear_extreme,
                        'trade_50_level': bear_50,
                        'extreme_high': price,
                        'trigger_tick_time': dt.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    self.risk.open_position(signal)
                    self.router.dispatch_entry(signal)
                    return {'type': 'ENTRY', 'signal': signal}

        return None

    def get_telemetry(self):
        """Returns live engine telemetry for the UI."""
        return {
            "tick_count": self.tick_count,
            "last_price": self.last_tick_price,
            "last_time": self.last_tick_time.strftime("%H:%M:%S") if self.last_tick_time else "---",
            "active_bar": self.current_bar,
            "in_trade": self.risk.in_trade,
            "bias": self.strategy.active_bias or "NEUTRAL",
            "bull_state": self.strategy.bull_state,
            "bear_state": self.strategy.bear_state
        }
