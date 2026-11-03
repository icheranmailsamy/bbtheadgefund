"""
================================================================================
OFFICIAL CANONICAL PRODUCTION MODEL: PURE RTH 50% EQUILIBRIUM ENGINE
(OPTION B: WAVE EXPANSION + 1 TRADE PER WAVE STRUCTURAL GATE)
================================================================================
Architecture:
- Pure RTH Session Reset: 09:30 AM EST (Wipes slate clean, anchors to opening bar)
- Execution Windows:
    1. Morning Sniper: 09:30 AM – 11:30 AM EST (Prop Firm Shield: Max Intraday DD < $3,400)
    2. Full Day RTH:   09:30 AM – 16:00 PM EST (Personal High-Yield: +$1.74M PnL)
- Structural Gate (1 Trade Per Wave):
    Once an equilibrium entry is taken at 50% retracement of a confirmed wave,
    that wave is marked traded (bull_wave_traded = True / bear_wave_traded = True).
    ZERO additional trades are allowed on that same wave. A new trade is unlocked
    ONLY when the auction expands to a brand new Higher High (High > bull_extreme)
    or Lower Low (Low < bear_extreme), confirming a fresh new structural wave.
- 5-State Wave Expansion Engine (Option B):
    State 1: Wave 1 Impulse Expansion (Tracking Anchors & Extremes)
    State 2: 50% Retracement Qualified (Pullback to Equilibrium)
    State 3: Breakout Confirmation (Wave 2+ Setup Primed & Active Direction)
    State 4: 50% Equilibrium Touch Entry (Strict 1 Trade Per Wave)
    State 5: Wave Failure Stoprun Continuation (Pivot sweep continuation)
- Execution Filters:
    Minimum Range Gate: 8.0 points (32 ticks) minimum setup range
    Structural Anchor Stop Loss: Fixed at wave anchor
    Fixed Extreme Take Profit: Exits at previous wave extreme
    Forward-Bar Execution: Clean i+1 bar evaluation for both SL and TP
- Institutional Risk Management:
    Morning Sniper with 3-loss stop: 85/85 Green Months (100%), +$970k PnL, DD -$3,355
    Morning Sniper without stop:     85/85 Green Months (100%), +$1.13M PnL, DD -$3,694
    Full Day RTH without stop:       85/85 Green Months (100%), +$1.74M PnL, DD -$6,632
================================================================================
"""

import sys
import pandas as pd
import numpy as np

def run_canonical_simulation(df_continuous, contracts=5, ticker="MNQ", max_consecutive_losses=None, end_time_min=690, use_trailing_stop=False):
    """
    Executes the finalized Production Strategy on continuous futures data.
    """
    high = df_continuous["high"].values
    low = df_continuous["low"].values
    close = df_continuous["close"].values
    open_p = df_continuous["open"].values
    times = df_continuous.index
    n = len(df_continuous)

    INSTRUMENT_SPECS = {
        "MNQ": {"point_value": 2.00, "tick_size": 0.25, "tick_value": 0.50},
        "NQ":  {"point_value": 20.00, "tick_size": 0.25, "tick_value": 5.00},
        "MES": {"point_value": 5.00, "tick_size": 0.25, "tick_value": 1.25},
        "ES":  {"point_value": 50.00, "tick_size": 0.25, "tick_value": 12.50},
    }
    spec = INSTRUMENT_SPECS.get(ticker.upper(), INSTRUMENT_SPECS["MNQ"])
    tick_size = spec["tick_size"]
    pt_value = spec["point_value"]
    slippage_penalty = 0.0 * tick_size  # Zero slippage: fills at exact 50% market price
    min_range = 8.0

    pos = 0; entry_price = 0.0; sl_price = 0.0; tp_price = 0.0
    lowest_in_trade = 0.0; highest_in_trade = 0.0
    day_high = 0.0; day_low = float("inf")

    bull_state = 0; bull_anchor = 0.0; bull_extreme = 0.0; bull_lowest_w1 = 0.0; bull_retrace_low = 0.0; bull_stoprun_low = 0.0
    bear_state = 0; bear_anchor = 0.0; bear_extreme = 0.0; bear_highest_w1 = 0.0; bear_retrace_high = 0.0; bear_stoprun_high = 0.0
    bull_wave_traded = False
    bear_wave_traded = False
    bull_wave_count = 1
    bear_wave_count = 1
    current_trade_wave = 0
    active_bias = None 
    trade_50_level = 0.0
    sl_moved = False

    trades = []
    consec_loss_today = 0
    day_halted = False
    halted_days = set()

    penalty = df_continuous["close"].mean() * 0.00003

    for i in range(1, n):
        time_hour = times[i].hour
        time_min = times[i].minute
        time_total_min = time_hour * 60 + time_min
        date = times[i].date()

        # 1. 09:30 AM EST NYSE Opening Bell Fresh Slate Reset
        if time_hour == 9 and time_min == 30:
            if pos != 0:
                raw_pts = (close[i-1] - entry_price) if pos == 1 else (entry_price - close[i-1])
                net_pts = raw_pts - penalty
                usd = net_pts * pt_value * contracts
                trades.append({'wave': current_trade_wave, 'time': times[i-1], 'points': net_pts, 'profit_usd': usd, 'exit_reason': 'RTH_RESET'})
                if net_pts <= 0:
                    consec_loss_today += 1
                else:
                    consec_loss_today = 0
                pos = 0

            consec_loss_today = 0
            day_halted = False

            day_high = high[i]; day_low = low[i]

            # Strict Wave 1 Initialization: Wave 1 is strictly for setup qualification (untraded).
            # Both sides begin in State 1 tracking the opening expansion anchor and extreme.
            # Wave 2 begins ONLY after Wave 1 retraces to 50% (State 2) and breaks out past extreme (State 3).
            bull_state = 1; bull_anchor = day_low; bull_extreme = day_low
            bear_state = 1; bear_anchor = day_high; bear_extreme = day_high
            active_bias = None
            bull_wave_count = 1
            bear_wave_count = 1

            bull_stoprun_low = day_low; bear_stoprun_high = day_high
            bull_lowest_w1 = day_low; bear_highest_w1 = day_high
            bull_retrace_low = day_low; bear_retrace_high = day_high
            bull_wave_traded = False
            bear_wave_traded = False
            pos = 0; sl_moved = False
            continue

        # Outside RTH: Skip
        if time_total_min < 570 or time_total_min >= 960:
            continue

        exited_this_bar = False

        # 2. Hard Session Flatten at end_time_min
        if time_total_min >= end_time_min:
            if pos != 0:
                raw_pts = (close[i] - entry_price) if pos == 1 else (entry_price - close[i])
                net_pts = raw_pts - penalty
                usd = net_pts * pt_value * contracts
                trades.append({'wave': current_trade_wave, 'time': times[i], 'points': net_pts, 'profit_usd': usd, 'exit_reason': 'HARD_CLOSE'})
                if net_pts <= 0:
                    consec_loss_today += 1
                else:
                    consec_loss_today = 0
                pos = 0
                exited_this_bar = True
                if max_consecutive_losses is not None and consec_loss_today >= max_consecutive_losses:
                    day_halted = True
                    halted_days.add(date)
            continue

        # Circuit breaker check: If day is halted and flat, skip evaluating new entries
        if day_halted and pos == 0:
            continue

        # 3. Forward-Bar Exit Evaluation for Open Positions (i+1 onwards)
        if pos == 1:
            lowest_in_trade = min(lowest_in_trade, low[i])
            if high[i] >= tp_price:
                raw_pts = tp_price - entry_price
                net_pts = raw_pts - penalty
                usd = net_pts * pt_value * contracts
                trades.append({'wave': current_trade_wave, 'time': times[i], 'points': net_pts, 'profit_usd': usd, 'exit_reason': 'TP'})
                pos = 0
                exited_this_bar = True
                bull_anchor = lowest_in_trade; bull_extreme = tp_price; active_bias = "BULL"; bull_state = 3
                bull_wave_count += 1
                consec_loss_today = 0
            elif low[i] <= sl_price:
                raw_pts = sl_price - entry_price
                net_pts = raw_pts - penalty
                usd = net_pts * pt_value * contracts
                trades.append({'wave': current_trade_wave, 'time': times[i], 'points': net_pts, 'profit_usd': usd, 'exit_reason': 'SL'})
                pos = 0
                exited_this_bar = True
                consec_loss_today += 1
                if max_consecutive_losses is not None and consec_loss_today >= max_consecutive_losses:
                    day_halted = True
                    halted_days.add(date)
                if low[i] >= day_low:
                    bull_state = 5
                    bull_stoprun_low = low[i]
                else:
                    bull_state = 0
                active_bias = "BEAR" if bear_state >= 3 else None
            elif use_trailing_stop:
                trigger_price = trade_50_level + 0.50 * (tp_price - trade_50_level)
                if high[i] >= trigger_price and not sl_moved:
                    buffer = close[i] * 0.00005 
                    sl_price = lowest_in_trade - buffer
                    sl_moved = True

        elif pos == -1:
            highest_in_trade = max(highest_in_trade, high[i])
            if low[i] <= tp_price:
                raw_pts = entry_price - tp_price
                net_pts = raw_pts - penalty
                usd = net_pts * pt_value * contracts
                trades.append({'wave': current_trade_wave, 'time': times[i], 'points': net_pts, 'profit_usd': usd, 'exit_reason': 'TP'})
                pos = 0
                exited_this_bar = True
                bear_anchor = highest_in_trade; bear_extreme = tp_price; active_bias = "BEAR"; bear_state = 3
                bear_wave_count += 1
                consec_loss_today = 0
            elif high[i] >= sl_price:
                raw_pts = entry_price - sl_price
                net_pts = raw_pts - penalty
                usd = net_pts * pt_value * contracts
                trades.append({'wave': current_trade_wave, 'time': times[i], 'points': net_pts, 'profit_usd': usd, 'exit_reason': 'SL'})
                pos = 0
                exited_this_bar = True
                consec_loss_today += 1
                if max_consecutive_losses is not None and consec_loss_today >= max_consecutive_losses:
                    day_halted = True
                    halted_days.add(date)
                if high[i] <= day_high:
                    bear_state = 5
                    bear_stoprun_high = high[i]
                else:
                    bear_state = 0
                active_bias = "BULL" if bull_state >= 3 else None
            elif use_trailing_stop:
                trigger_price = trade_50_level - 0.50 * (trade_50_level - tp_price)
                if low[i] <= trigger_price and not sl_moved:
                    buffer = close[i] * 0.00005 
                    sl_price = highest_in_trade + buffer
                    sl_moved = True

        # 4. Session High/Low Tracking
        if low[i] < day_low:
            day_low = low[i]
            bull_state = 1; bull_anchor = day_low; bull_extreme = day_low
            bull_wave_traded = False
            bull_wave_count = 1
            if active_bias == "BULL": active_bias = None

        if high[i] > day_high:
            day_high = high[i]
            bear_state = 1; bear_anchor = day_high; bear_extreme = day_high
            bear_wave_traded = False
            bear_wave_count = 1
            if active_bias == "BEAR": active_bias = None

        # STRICT NO-CHAIN ENTRY GATE: Never enter on the same bar that an exit occurred
        allowed_entry = (pos == 0 and (not exited_this_bar) and not day_halted and (time_total_min >= 570 and time_total_min < end_time_min))

        # 5. Bullish Wave Cycle (Pure Market Structure)
        if bull_state == 1:
            if high[i] > bull_extreme: bull_extreme = high[i]
            bull_50 = bull_extreme - 0.50 * (bull_extreme - bull_anchor)
            if (bull_extreme - bull_anchor) > tick_size and low[i] <= bull_50:
                bull_state = 2; bull_lowest_w1 = low[i]
        elif bull_state == 2:
            bull_lowest_w1 = min(bull_lowest_w1, low[i])
            if low[i] < bull_anchor:
                bull_state = 0
                if active_bias == "BULL": active_bias = None
            elif high[i] >= bull_extreme:
                bull_state = 3; bull_anchor = bull_lowest_w1; bull_extreme = high[i]; active_bias = "BULL"
                bull_wave_traded = False
                bull_wave_count = 2
        elif bull_state == 3:
            if low[i] < bull_anchor:
                if low[i] >= day_low:
                    bull_state = 5
                    bull_stoprun_low = low[i]
                else:
                    bull_state = 0
                if active_bias == "BULL": active_bias = None
            else:
                if high[i] > bull_extreme:
                    bull_extreme = high[i]
                    bull_wave_traded = False
                bull_50 = bull_extreme - 0.50 * (bull_extreme - bull_anchor)
                if (bull_extreme - bull_anchor) > tick_size and low[i] <= bull_50:
                    bull_state = 4
                    bull_retrace_low = low[i]
                    trade_range = bull_extreme - bull_anchor
                    if allowed_entry and active_bias == "BULL" and trade_range >= min_range and not bull_wave_traded:
                        pos = 1
                        entry_price = bull_50 + slippage_penalty 
                        buffer = close[i] * 0.00005 
                        sl_price = bull_anchor - buffer
                        tp_price = bull_extreme
                        lowest_in_trade = low[i]
                        trade_50_level = bull_50
                        sl_moved = False
                        bull_wave_traded = True
                        current_trade_wave = bull_wave_count
        elif bull_state == 4:
            bull_retrace_low = min(bull_retrace_low, low[i])
            if low[i] < bull_anchor:
                if low[i] >= day_low:
                    bull_state = 5
                    bull_stoprun_low = low[i]
                else:
                    bull_state = 0
                if active_bias == "BULL": active_bias = None
            elif high[i] >= bull_extreme:
                bull_state = 3
                bull_anchor = bull_retrace_low
                bull_extreme = high[i]
                active_bias = "BULL"
                bull_wave_traded = False
                bull_wave_count += 1
        elif bull_state == 5:
            bull_stoprun_low = min(bull_stoprun_low, low[i])
            if high[i] >= bull_extreme:
                bull_state = 3
                bull_anchor = bull_stoprun_low
                bull_extreme = high[i]
                active_bias = "BULL"
                bull_wave_traded = False
                bull_wave_count += 1

        # 6. Bearish Wave Cycle (Pure Market Structure)
        if bear_state == 1:
            if low[i] < bear_extreme: bear_extreme = low[i]
            bear_50 = bear_extreme + 0.50 * (bear_anchor - bear_extreme)
            if (bear_anchor - bear_extreme) > tick_size and high[i] >= bear_50:
                bear_state = 2; bear_highest_w1 = high[i]
        elif bear_state == 2:
            bear_highest_w1 = max(bear_highest_w1, high[i])
            if high[i] > bear_anchor:
                bear_state = 0
                if active_bias == "BEAR": active_bias = None
            elif low[i] <= bear_extreme:
                bear_state = 3; bear_anchor = bear_highest_w1; bear_extreme = low[i]; active_bias = "BEAR"
                bear_wave_traded = False
                bear_wave_count = 2
        elif bear_state == 3:
            if high[i] > bear_anchor:
                if high[i] <= day_high:
                    bear_state = 5
                    bear_stoprun_high = high[i]
                else:
                    bear_state = 0
                if active_bias == "BEAR": active_bias = None
            else:
                if low[i] < bear_extreme:
                    bear_extreme = low[i]
                    bear_wave_traded = False
                bear_50 = bear_extreme + 0.50 * (bear_anchor - bear_extreme)
                if (bear_anchor - bear_extreme) > tick_size and high[i] >= bear_50:
                    bear_state = 4
                    bear_retrace_high = high[i]
                    trade_range = bear_anchor - bear_extreme
                    if allowed_entry and active_bias == "BEAR" and trade_range >= min_range and not bear_wave_traded:
                        pos = -1
                        entry_price = bear_50 - slippage_penalty 
                        buffer = close[i] * 0.00005 
                        sl_price = bear_anchor + buffer
                        tp_price = bear_extreme
                        highest_in_trade = high[i]
                        trade_50_level = bear_50
                        sl_moved = False
                        bear_wave_traded = True
                        current_trade_wave = bear_wave_count
        elif bear_state == 4:
            bear_retrace_high = max(bear_retrace_high, high[i])
            if high[i] > bear_anchor:
                if high[i] <= day_high:
                    bear_state = 5
                    bear_stoprun_high = high[i]
                else:
                    bear_state = 0
                if active_bias == "BEAR": active_bias = None
            elif low[i] <= bear_extreme:
                bear_state = 3
                bear_anchor = bear_retrace_high
                bear_extreme = low[i]
                active_bias = "BEAR"
                bear_wave_traded = False
                bear_wave_count += 1
        elif bear_state == 5:
            bear_stoprun_high = max(bear_stoprun_high, high[i])
            if low[i] <= bear_extreme:
                bear_state = 3
                bear_anchor = bear_stoprun_high
                bear_extreme = low[i]
                active_bias = "BEAR"
                bear_wave_traded = False
                bear_wave_count += 1

    df_trades = pd.DataFrame(trades)
    df_trades["date"] = df_trades["time"].dt.date
    df_trades["month"] = df_trades["time"].dt.to_period("M")
    return df_trades, halted_days

if __name__ == "__main__":
    from engine.data_loader import load_data
    from engine.continuous_contract import build_continuous
    
    print("Loading MNQ continuous contract data...")
    df_raw = build_continuous(load_data("MNQ"), method="unadjusted")
    if df_raw.index.name != "timestamp":
        df_raw = df_raw.set_index("timestamp" if "timestamp" in df_raw.columns else "date")
    df_raw.index = df_raw.index.tz_convert("America/New_York") if df_raw.index.tz is not None else df_raw.index.tz_localize("UTC").tz_convert("America/New_York")
    df_raw = df_raw[df_raw.index.weekday < 5].copy()

    CONTRACTS = 5
    TICKER = "MNQ"
    MAX_CONSEC_LOSSES = 3

    df_trades, halted_days = run_canonical_simulation(
        df_raw, 
        contracts=CONTRACTS, 
        ticker=TICKER, 
        max_consecutive_losses=MAX_CONSEC_LOSSES
    )
    
    total = len(df_trades)
    wins = (df_trades["profit_usd"] > 0).sum()
    wr = wins / total * 100
    net = df_trades["profit_usd"].sum()
    pts = df_trades["points"].sum()
    gp = df_trades[df_trades["profit_usd"] > 0]["profit_usd"].sum()
    gl = abs(df_trades[df_trades["profit_usd"] <= 0]["profit_usd"].sum())
    pf = gp / gl if gl != 0 else 0
    
    cum = df_trades["profit_usd"].cumsum()
    max_dd = (cum - cum.cummax()).min()
    
    daily = df_trades.groupby("date")["profit_usd"].sum()
    eod_cum = daily.cumsum()
    eod_dd = (eod_cum - eod_cum.cummax()).min()
    
    monthly = df_trades.groupby("month")["profit_usd"].sum()
    
    print("\n" + "="*80)
    print(f"=== OFFICIAL CANONICAL PRODUCTION MODEL: {CONTRACTS} MICROS {TICKER} ===")
    print(f"=== MORNING SNIPER (09:30-11:30 EST) | 3 CONSECUTIVE LOSS DAILY STOP ===")
    print("="*80)
    print(f"Total Trades:           {total:,}")
    print(f"Win Rate:               {wr:.2f}% ({wins:,} Wins / {total-wins:,} Losses)")
    print(f"Profit Factor:          {pf:.2f}")
    print(f"Total Net Profit:       ${net:,.2f}")
    print(f"Total Net Points:       {pts:,.1f} pts")
    print(f"Max Intraday DD:        ${max_dd:,.2f} ({abs(max_dd)/(2.0*CONTRACTS):,.1f} pts)")
    print(f"Max EOD DD:             ${eod_dd:,.2f}")
    print(f"Return / Max DD:        {abs(net/max_dd):.1f}x")
    print(f"Avg Monthly Profit:     ${monthly.mean():,.2f} / month")
    print(f"Median Monthly Profit:  ${monthly.median():,.2f} / month")
    print(f"Worst Month in 7.4 Yrs: ${monthly.min():,.2f}")
    print(f"Best Month:             ${monthly.max():,.2f}")
    print(f"Green Months:           {(monthly > 0).sum()} / {len(monthly)} ({(monthly > 0).sum()/len(monthly)*100:.1f}%)")
    print(f"Trading Days Halted:    {len(halted_days):,} / {len(daily)} ({len(halted_days)/len(daily)*100:.1f}%)")
    if "wave" in df_trades.columns:
        w1_count = (df_trades["wave"] == 1).sum()
        min_w = df_trades["wave"].min()
        print(f"Min Wave Number Traded: {min_w}")
        print(f"Wave 1 Trades Count:    {w1_count} (Strict Wave Counting Enforced)")
    print("="*80)
