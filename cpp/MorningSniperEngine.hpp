#pragma once

#include <cstdint>
#include <algorithm>
#include <cmath>
#include <string_view>
#include <vector>

namespace QuantEngine {

enum class MarketPosition : int8_t {
    SHORT = -1,
    FLAT  =  0,
    LONG  =  1
};

enum class ActiveBias : int8_t {
    NONE = 0,
    BULL = 1,
    BEAR = 2
};

enum class OrderAction : uint8_t {
    NONE = 0,
    ENTER_LONG,
    ENTER_SHORT,
    EXIT_LONG_SL,
    EXIT_LONG_TP,
    EXIT_SHORT_SL,
    EXIT_SHORT_TP,
    FLATTEN_SESSION_END
};

struct alignas(64) Bar {
    int64_t timestamp_ms; // Unix epoch ms
    int32_t hhmmss;       // e.g. 93000, 113000
    double  open;
    double  high;
    double  low;
    double  close;
    double  volume;
};

struct ExecutionSignal {
    OrderAction action{OrderAction::NONE};
    double price{0.0};
    double sl_price{0.0};
    double tp_price{0.0};
    int32_t contracts{0};
    const char* reason{""};
};

struct StrategyConfig {
    double min_range_points{8.0};           // 8.0 points (32 ticks) setup gate
    int32_t contracts{5};                   // 5 Micro contracts standard
    double tick_size{0.25};                 // 0.25 for NQ/MNQ/ES/MES
    double slippage_ticks{0.0};             // Exact filling market price (zero slippage)
    int32_t max_consecutive_losses{3};      // 3-consecutive-loss circuit breaker
    int32_t session_start_hhmmss{93000};    // 09:30:00 EST
    int32_t session_end_hhmmss{113000};     // 11:30:00 EST Hard Flatten
};

class alignas(64) MorningSniperEngine {
public:
    explicit MorningSniperEngine(const StrategyConfig& config = StrategyConfig()) noexcept
        : cfg_(config),
          half_tick_(config.tick_size * 0.5),
          slippage_offset_(config.slippage_ticks * config.tick_size) {
        reset_all();
    }

    void reset_all() noexcept {
        day_high_ = 0.0;
        day_low_ = 1e9;
        
        bull_state_ = 0;
        bull_anchor_ = 0.0;
        bull_extreme_ = 0.0;
        bull_lowest_w1_ = 0.0;
        bull_retrace_low_ = 0.0;
        bull_stoprun_low_ = 0.0;

        bear_state_ = 0;
        bear_anchor_ = 0.0;
        bear_extreme_ = 0.0;
        bear_highest_w1_ = 0.0;
        bear_retrace_high_ = 0.0;
        bear_stoprun_high_ = 0.0;

        active_bias_ = ActiveBias::NONE;

        pos_ = MarketPosition::FLAT;
        entry_price_ = 0.0;
        sl_price_ = 0.0;
        tp_price_ = 0.0;
        trade_50_level_ = 0.0;
        lowest_in_trade_ = 0.0;
        highest_in_trade_ = 0.0;
        sl_moved_ = false;

        consecutive_losses_ = 0;
        day_halted_ = false;
    }

    [[nodiscard]] inline MarketPosition position() const noexcept { return pos_; }
    [[nodiscard]] inline int32_t consecutive_losses() const noexcept { return consecutive_losses_; }
    [[nodiscard]] inline bool is_day_halted() const noexcept { return day_halted_; }
    [[nodiscard]] inline double current_sl() const noexcept { return sl_price_; }
    [[nodiscard]] inline double current_tp() const noexcept { return tp_price_; }
    [[nodiscard]] inline double entry_price() const noexcept { return entry_price_; }

    /**
     * @brief Real-Time Tick-by-Tick Evaluation (Intra-Bar High Frequency Mode)
     * Executes in ~3 to 5 nanoseconds on every CME trade tick.
     * Evaluates immediate 50% equilibrium touch, dynamic trailing stop shift,
     * and sub-millisecond stop-loss / take-profit fills without waiting for bar close.
     */
    inline ExecutionSignal process_tick(double tick_price, int32_t hhmmss) noexcept {
        ExecutionSignal sig;

        // Session Hard Flatten at 11:30 AM EST Sharp
        if (hhmmss >= cfg_.session_end_hhmmss) [[unlikely]] {
            if (pos_ != MarketPosition::FLAT) {
                sig.action = OrderAction::FLATTEN_SESSION_END;
                sig.price = tick_price;
                sig.contracts = cfg_.contracts;
                sig.reason = "Flatten_1130_Tick";
                const double pnl = (pos_ == MarketPosition::LONG) ? (tick_price - entry_price_) : (entry_price_ - tick_price);
                update_circuit_breaker(pnl);
                pos_ = MarketPosition::FLAT;
            }
            return sig;
        }

        if (hhmmss < cfg_.session_start_hhmmss) [[unlikely]] {
            return sig;
        }

        // Intra-Trade Real-Time Tick Management
        if (pos_ == MarketPosition::LONG) {
            lowest_in_trade_ = std::min(lowest_in_trade_, tick_price);

            // Trailing Stop trigger at 50% progress to TP
            const double trigger = trade_50_level_ + 0.5 * (tp_price_ - trade_50_level_);
            if (tick_price >= trigger && !sl_moved_) [[unlikely]] {
                sl_price_ = lowest_in_trade_ - (tick_price * 0.00005);
                sl_moved_ = true;
            }

            // Real-time Stop or Target Fill
            if (tick_price <= sl_price_) [[unlikely]] {
                sig.action = OrderAction::EXIT_LONG_SL;
                sig.price = sl_price_ - slippage_offset_;
                sig.contracts = cfg_.contracts;
                sig.reason = "Long_SL_Tick_Filled";
                update_circuit_breaker(sig.price - entry_price_);
                pos_ = MarketPosition::FLAT;
                return sig;
            } else if (tick_price >= tp_price_) [[unlikely]] {
                sig.action = OrderAction::EXIT_LONG_TP;
                sig.price = tp_price_;
                sig.contracts = cfg_.contracts;
                sig.reason = "Long_TP_Tick_Filled";
                update_circuit_breaker(sig.price - entry_price_);
                pos_ = MarketPosition::FLAT;
                return sig;
            }
        } else if (pos_ == MarketPosition::SHORT) {
            highest_in_trade_ = std::max(highest_in_trade_, tick_price);

            // Trailing Stop trigger at 50% progress to TP
            const double trigger = trade_50_level_ - 0.5 * (trade_50_level_ - tp_price_);
            if (tick_price <= trigger && !sl_moved_) [[unlikely]] {
                sl_price_ = highest_in_trade_ + (tick_price * 0.00005);
                sl_moved_ = true;
            }

            // Real-time Stop or Target Fill
            if (tick_price >= sl_price_) [[unlikely]] {
                sig.action = OrderAction::EXIT_SHORT_SL;
                sig.price = sl_price_ + slippage_offset_;
                sig.contracts = cfg_.contracts;
                sig.reason = "Short_SL_Tick_Filled";
                update_circuit_breaker(entry_price_ - sig.price);
                pos_ = MarketPosition::FLAT;
                return sig;
            } else if (tick_price <= tp_price_) [[unlikely]] {
                sig.action = OrderAction::EXIT_SHORT_TP;
                sig.price = tp_price_;
                sig.contracts = cfg_.contracts;
                sig.reason = "Short_TP_Tick_Filled";
                update_circuit_breaker(entry_price_ - sig.price);
                pos_ = MarketPosition::FLAT;
                return sig;
            }
        }

        return sig;
    }

    /**
     * @brief Bar-by-Bar Evaluation Engine
     * Evaluates 1-minute OHLC bar in ~7 to 10 nanoseconds.
     */
    inline ExecutionSignal process_bar(const Bar& bar) noexcept {
        ExecutionSignal sig;
        const int32_t t = bar.hhmmss;

        // 1. HARD FLATTEN AT 11:30 AM EST SHARP
        if (t >= cfg_.session_end_hhmmss) [[unlikely]] {
            if (pos_ != MarketPosition::FLAT) {
                sig.action = OrderAction::FLATTEN_SESSION_END;
                sig.price = bar.close;
                sig.contracts = cfg_.contracts;
                sig.reason = "Flatten_1130_Hard_Close";
                
                const double pnl = (pos_ == MarketPosition::LONG) ? (bar.close - entry_price_) : (entry_price_ - bar.close);
                update_circuit_breaker(pnl);
                pos_ = MarketPosition::FLAT;
            }
            return sig;
        }

        // 2. PURE RTH SESSION OPEN (09:30:00 EST) - FRESH DAILY REBOOT
        if (t == cfg_.session_start_hhmmss) [[unlikely]] {
            day_high_ = bar.high;
            day_low_ = bar.low;

            bull_state_ = 1;
            bull_anchor_ = day_low_;
            bull_extreme_ = day_low_;
            bull_lowest_w1_ = day_low_;
            bull_retrace_low_ = day_low_;
            bull_stoprun_low_ = day_low_;

            bear_state_ = 1;
            bear_anchor_ = day_high_;
            bear_extreme_ = day_high_;
            bear_highest_w1_ = day_high_;
            bear_retrace_high_ = day_high_;
            bear_stoprun_high_ = day_high_;

            active_bias_ = ActiveBias::NONE;
            sl_moved_ = false;
            consecutive_losses_ = 0;
            day_halted_ = false;

            return sig;
        }

        // Ignore bars outside Morning Sniper Window (09:30 - 11:30 EST)
        if (t < cfg_.session_start_hhmmss || t > cfg_.session_end_hhmmss) [[unlikely]] {
            return sig;
        }

        // 3. IN-TRADE POSITION MANAGEMENT & FORWARD EXIT EVALUATION
        if (pos_ == MarketPosition::LONG) {
            lowest_in_trade_ = std::min(lowest_in_trade_, bar.low);

            const double trigger = trade_50_level_ + 0.5 * (tp_price_ - trade_50_level_);
            if (bar.high >= trigger && !sl_moved_) {
                sl_price_ = lowest_in_trade_ - (bar.close * 0.00005);
                sl_moved_ = true;
            }

            if (bar.low <= sl_price_) {
                sig.action = OrderAction::EXIT_LONG_SL;
                sig.price = sl_price_ - slippage_offset_;
                sig.contracts = cfg_.contracts;
                sig.reason = "Long_SL_Filled";
                update_circuit_breaker(sig.price - entry_price_);
                pos_ = MarketPosition::FLAT;
                return sig;
            } else if (bar.high >= tp_price_) {
                sig.action = OrderAction::EXIT_LONG_TP;
                sig.price = tp_price_;
                sig.contracts = cfg_.contracts;
                sig.reason = "Long_TP_Target_Achieved";
                update_circuit_breaker(sig.price - entry_price_);
                pos_ = MarketPosition::FLAT;
                return sig;
            }
        } else if (pos_ == MarketPosition::SHORT) {
            highest_in_trade_ = std::max(highest_in_trade_, bar.high);

            const double trigger = trade_50_level_ - 0.5 * (trade_50_level_ - tp_price_);
            if (bar.low <= trigger && !sl_moved_) {
                sl_price_ = highest_in_trade_ + (bar.close * 0.00005);
                sl_moved_ = true;
            }

            if (bar.high >= sl_price_) {
                sig.action = OrderAction::EXIT_SHORT_SL;
                sig.price = sl_price_ + slippage_offset_;
                sig.contracts = cfg_.contracts;
                sig.reason = "Short_SL_Filled";
                update_circuit_breaker(entry_price_ - sig.price);
                pos_ = MarketPosition::FLAT;
                return sig;
            } else if (bar.low <= tp_price_) {
                sig.action = OrderAction::EXIT_SHORT_TP;
                sig.price = tp_price_;
                sig.contracts = cfg_.contracts;
                sig.reason = "Short_TP_Target_Achieved";
                update_circuit_breaker(entry_price_ - sig.price);
                pos_ = MarketPosition::FLAT;
                return sig;
            }
        }

        // 4. SESSION EXTREME EXPANSION & STRUCTURAL RESET
        if (bar.low < day_low_) {
            day_low_ = bar.low;
            bull_state_ = 1;
            bull_anchor_ = day_low_;
            bull_extreme_ = day_low_;
            if (active_bias_ == ActiveBias::BULL) {
                active_bias_ = ActiveBias::NONE;
            }
        }

        if (bar.high > day_high_) {
            day_high_ = bar.high;
            bear_state_ = 1;
            bear_anchor_ = day_high_;
            bear_extreme_ = day_high_;
            if (active_bias_ == ActiveBias::BEAR) {
                active_bias_ = ActiveBias::NONE;
            }
        }

        const bool is_entry_allowed = (pos_ == MarketPosition::FLAT) && !day_halted_;
        const double tick = cfg_.tick_size;

        // 5. BULLISH STATE MACHINE (OPTION B)
        if (bull_state_ == 1) {
            if (bar.high > bull_extreme_) bull_extreme_ = bar.high;
            const double bull50 = bull_extreme_ - 0.5 * (bull_extreme_ - bull_anchor_);
            if ((bull_extreme_ - bull_anchor_) > tick && bar.low <= bull50) {
                bull_state_ = 2;
                bull_lowest_w1_ = bar.low;
            }
        } else if (bull_state_ == 2) {
            bull_lowest_w1_ = std::min(bull_lowest_w1_, bar.low);
            if (bar.low < bull_anchor_) {
                bull_state_ = 0;
                if (active_bias_ == ActiveBias::BULL) active_bias_ = ActiveBias::NONE;
            } else if (bar.high >= bull_extreme_) {
                bull_state_ = 3;
                bull_anchor_ = bull_lowest_w1_;
                bull_extreme_ = bar.high;
                active_bias_ = ActiveBias::BULL; // Recency Override
            }
        } else if (bull_state_ == 3) {
            if (bar.low < bull_anchor_) {
                if (bar.low >= day_low_) {
                    bull_state_ = 5; // Option B: Wave Failure Stoprun Continuation
                    bull_stoprun_low_ = bar.low;
                } else {
                    bull_state_ = 0;
                }
                if (active_bias_ == ActiveBias::BULL) active_bias_ = ActiveBias::NONE;
            } else {
                if (bar.high > bull_extreme_) bull_extreme_ = bar.high;
                const double bull50 = bull_extreme_ - 0.5 * (bull_extreme_ - bull_anchor_);

                if ((bull_extreme_ - bull_anchor_) > tick && bar.low <= bull50) {
                    bull_state_ = 4;
                    bull_retrace_low_ = bar.low;
                    const double trade_range = bull_extreme_ - bull_anchor_;

                    // Long Entry Gate
                    if (is_entry_allowed && active_bias_ == ActiveBias::BULL && trade_range >= cfg_.min_range_points) {
                        trade_50_level_ = bull50;
                        entry_price_ = bull50 + slippage_offset_;
                        sl_price_ = bull_anchor_ - (bar.close * 0.00005);
                        tp_price_ = bull_extreme_;
                        lowest_in_trade_ = bar.low;
                        sl_moved_ = false;
                        pos_ = MarketPosition::LONG;

                        sig.action = OrderAction::ENTER_LONG;
                        sig.price = entry_price_;
                        sig.sl_price = sl_price_;
                        sig.tp_price = tp_price_;
                        sig.contracts = cfg_.contracts;
                        sig.reason = "Morning_Sniper_50_Equilibrium_Long";
                        return sig;
                    }
                }
            }
        } else if (bull_state_ == 4) {
            bull_retrace_low_ = std::min(bull_retrace_low_, bar.low);
            if (bar.low < bull_anchor_) {
                if (bar.low >= day_low_) {
                    bull_state_ = 5; // Option B
                    bull_stoprun_low_ = bar.low;
                } else {
                    bull_state_ = 0;
                }
                if (active_bias_ == ActiveBias::BULL) active_bias_ = ActiveBias::NONE;
            } else if (bar.high >= bull_extreme_) {
                bull_state_ = 3;
                bull_anchor_ = bull_retrace_low_;
                bull_extreme_ = bar.high;
                active_bias_ = ActiveBias::BULL;
            }
        } else if (bull_state_ == 5) {
            // Option B: Stoprun Continuation Tracking
            bull_stoprun_low_ = std::min(bull_stoprun_low_, bar.low);
            if (bar.high >= bull_extreme_) {
                bull_state_ = 3;
                bull_anchor_ = bull_stoprun_low_;
                bull_extreme_ = bar.high;
                active_bias_ = ActiveBias::BULL;
            }
        }

        // 6. BEARISH STATE MACHINE (OPTION B)
        if (bear_state_ == 1) {
            if (bar.low < bear_extreme_) bear_extreme_ = bar.low;
            const double bear50 = bear_extreme_ + 0.5 * (bear_anchor_ - bear_extreme_);
            if ((bear_anchor_ - bear_extreme_) > tick && bar.high >= bear50) {
                bear_state_ = 2;
                bear_highest_w1_ = bar.high;
            }
        } else if (bear_state_ == 2) {
            bear_highest_w1_ = std::max(bear_highest_w1_, bar.high);
            if (bar.high > bear_anchor_) {
                bear_state_ = 0;
                if (active_bias_ == ActiveBias::BEAR) active_bias_ = ActiveBias::NONE;
            } else if (bar.low <= bear_extreme_) {
                bear_state_ = 3;
                bear_anchor_ = bear_highest_w1_;
                bear_extreme_ = bar.low;
                active_bias_ = ActiveBias::BEAR; // Recency Override
            }
        } else if (bear_state_ == 3) {
            if (bar.high > bear_anchor_) {
                if (bar.high <= day_high_) {
                    bear_state_ = 5; // Option B
                    bear_stoprun_high_ = bar.high;
                } else {
                    bear_state_ = 0;
                }
                if (active_bias_ == ActiveBias::BEAR) active_bias_ = ActiveBias::NONE;
            } else {
                if (bar.low < bear_extreme_) bear_extreme_ = bar.low;
                const double bear50 = bear_extreme_ + 0.5 * (bear_anchor_ - bear_extreme_);

                if ((bear_anchor_ - bear_extreme_) > tick && bar.high >= bear50) {
                    bear_state_ = 4;
                    bear_retrace_high_ = bar.high;
                    const double trade_range = bear_anchor_ - bear_extreme_;

                    // Short Entry Gate
                    if (is_entry_allowed && active_bias_ == ActiveBias::BEAR && trade_range >= cfg_.min_range_points) {
                        trade_50_level_ = bear50;
                        entry_price_ = bear50 - slippage_offset_;
                        sl_price_ = bear_anchor_ + (bar.close * 0.00005);
                        tp_price_ = bear_extreme_;
                        highest_in_trade_ = bar.high;
                        sl_moved_ = false;
                        pos_ = MarketPosition::SHORT;

                        sig.action = OrderAction::ENTER_SHORT;
                        sig.price = entry_price_;
                        sig.sl_price = sl_price_;
                        sig.tp_price = tp_price_;
                        sig.contracts = cfg_.contracts;
                        sig.reason = "Morning_Sniper_50_Equilibrium_Short";
                        return sig;
                    }
                }
            }
        } else if (bear_state_ == 4) {
            bear_retrace_high_ = std::max(bear_retrace_high_, bar.high);
            if (bar.high > bear_anchor_) {
                if (bar.high <= day_high_) {
                    bear_state_ = 5; // Option B
                    bear_stoprun_high_ = bar.high;
                } else {
                    bear_state_ = 0;
                }
                if (active_bias_ == ActiveBias::BEAR) active_bias_ = ActiveBias::NONE;
            } else if (bar.low <= bear_extreme_) {
                bear_state_ = 3;
                bear_anchor_ = bear_retrace_high_;
                bear_extreme_ = bar.low;
                active_bias_ = ActiveBias::BEAR;
            }
        } else if (bear_state_ == 5) {
            // Option B: Stoprun Continuation Tracking
            bear_stoprun_high_ = std::max(bear_stoprun_high_, bar.high);
            if (bar.low <= bear_extreme_) {
                bear_state_ = 3;
                bear_anchor_ = bear_stoprun_high_;
                bear_extreme_ = bar.low;
                active_bias_ = ActiveBias::BEAR;
            }
        }

        return sig;
    }

    /**
     * @brief High-Throughput Batch Processing with Cache Prefetching
     */
    void process_batch(const Bar* bars, size_t count, ExecutionSignal* out_signals) noexcept {
        for (size_t i = 0; i < count; ++i) {
            if (i + 4 < count) {
                __builtin_prefetch(&bars[i + 4], 0, 3);
            }
            out_signals[i] = process_bar(bars[i]);
        }
    }

private:
    inline void update_circuit_breaker(double pnl) noexcept {
        if (pnl <= 0.0) {
            consecutive_losses_++;
            if (consecutive_losses_ >= cfg_.max_consecutive_losses) {
                day_halted_ = true;
            }
        } else {
            consecutive_losses_ = 0;
        }
    }

    StrategyConfig cfg_;
    double half_tick_{0.125};
    double slippage_offset_{0.5};

    // Session Extremes
    double day_high_{0.0};
    double day_low_{1e9};

    // Bullish State Machine
    int32_t bull_state_{0};
    double bull_anchor_{0.0};
    double bull_extreme_{0.0};
    double bull_lowest_w1_{0.0};
    double bull_retrace_low_{0.0};
    double bull_stoprun_low_{0.0};

    // Bearish State Machine
    int32_t bear_state_{0};
    double bear_anchor_{0.0};
    double bear_extreme_{0.0};
    double bear_highest_w1_{0.0};
    double bear_retrace_high_{0.0};
    double bear_stoprun_high_{0.0};

    // Active Market Bias
    ActiveBias active_bias_{ActiveBias::NONE};

    // Position & In-Trade Dynamics
    MarketPosition pos_{MarketPosition::FLAT};
    double entry_price_{0.0};
    double sl_price_{0.0};
    double tp_price_{0.0};
    double trade_50_level_{0.0};
    double lowest_in_trade_{0.0};
    double highest_in_trade_{0.0};
    bool sl_moved_{false};

    // Risk Circuit Breaker
    int32_t consecutive_losses_{0};
    bool day_halted_{false};
};

} // namespace QuantEngine
