#include "MorningSniperEngine.hpp"

extern "C" {

struct CEvalResult {
    int32_t action;        // 0=None, 1=Long, 2=Short, 3=ExitLongSL, 4=ExitLongTP, 5=ExitShortSL, 6=ExitShortTP, 7=Flatten
    double price;
    double sl_price;
    double tp_price;
    int32_t contracts;
    int32_t consecutive_losses;
    int32_t is_halted;
};

// Create strategy instance
QuantEngine::MorningSniperEngine* create_engine(
    double min_range,
    int32_t contracts,
    double tick_size,
    double slippage_ticks,
    int32_t max_losses,
    int32_t start_time,
    int32_t end_time
) {
    QuantEngine::StrategyConfig cfg;
    cfg.min_range_points = min_range;
    cfg.contracts = contracts;
    cfg.tick_size = tick_size;
    cfg.slippage_ticks = slippage_ticks;
    cfg.max_consecutive_losses = max_losses;
    cfg.session_start_hhmmss = start_time;
    cfg.session_end_hhmmss = end_time;

    return new QuantEngine::MorningSniperEngine(cfg);
}

void destroy_engine(QuantEngine::MorningSniperEngine* engine) {
    delete engine;
}

void reset_engine(QuantEngine::MorningSniperEngine* engine) {
    if (engine) engine->reset_all();
}

CEvalResult process_tick_c(
    QuantEngine::MorningSniperEngine* engine,
    double tick_price,
    int32_t hhmmss
) {
    CEvalResult res{};
    if (!engine) return res;

    auto sig = engine->process_tick(tick_price, hhmmss);
    res.action = static_cast<int32_t>(sig.action);
    res.price = sig.price;
    res.sl_price = sig.sl_price;
    res.tp_price = sig.tp_price;
    res.contracts = sig.contracts;
    res.consecutive_losses = engine->consecutive_losses();
    res.is_halted = engine->is_day_halted() ? 1 : 0;

    return res;
}

CEvalResult process_bar_c(
    QuantEngine::MorningSniperEngine* engine,
    int64_t timestamp_ms,
    int32_t hhmmss,
    double open,
    double high,
    double low,
    double close,
    double volume
) {
    CEvalResult res{};
    if (!engine) return res;

    QuantEngine::Bar bar;
    bar.timestamp_ms = timestamp_ms;
    bar.hhmmss = hhmmss;
    bar.open = open;
    bar.high = high;
    bar.low = low;
    bar.close = close;
    bar.volume = volume;

    auto sig = engine->process_bar(bar);
    res.action = static_cast<int32_t>(sig.action);
    res.price = sig.price;
    res.sl_price = sig.sl_price;
    res.tp_price = sig.tp_price;
    res.contracts = sig.contracts;
    res.consecutive_losses = engine->consecutive_losses();
    res.is_halted = engine->is_day_halted() ? 1 : 0;

    return res;
}

} // extern "C"
