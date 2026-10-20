#include "MorningSniperEngine.hpp"
#include <iostream>
#include <chrono>
#include <vector>
#include <random>
#include <iomanip>

int main() {
    std::cout << "========================================================\n";
    std::cout << "  C++20 MORNING SNIPER QUANT ENGINE - SPEED BENCHMARK    \n";
    std::cout << "========================================================\n";

    QuantEngine::StrategyConfig cfg;
    cfg.contracts = 5;
    cfg.max_consecutive_losses = 3;
    cfg.min_range_points = 8.0;

    QuantEngine::MorningSniperEngine engine(cfg);

    const size_t NUM_TICKS = 10'000'000;
    std::cout << "[BENCHMARK] Generating and processing " << NUM_TICKS << " real-time price ticks...\n";

    std::vector<double> ticks;
    ticks.reserve(NUM_TICKS);

    double p = 21000.0;
    std::mt19937_64 rng(1337);
    std::normal_distribution<double> dist(0.0, 0.5);

    for (size_t i = 0; i < NUM_TICKS; ++i) {
        p += dist(rng);
        ticks.push_back(p);
    }

    int64_t tick_signals = 0;
    const auto t_start_tick = std::chrono::high_resolution_clock::now();

    for (size_t i = 0; i < NUM_TICKS; ++i) {
        auto sig = engine.process_tick(ticks[i], 100000);
        if (sig.action != QuantEngine::OrderAction::NONE) {
            tick_signals++;
        }
    }

    const auto t_end_tick = std::chrono::high_resolution_clock::now();
    const auto duration_tick_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(t_end_tick - t_start_tick).count();
    const double ns_per_tick = static_cast<double>(duration_tick_ns) / NUM_TICKS;
    const double ticks_per_sec = (static_cast<double>(NUM_TICKS) / duration_tick_ns) * 1e9;

    std::cout << std::fixed << std::setprecision(2);
    std::cout << "--------------------------------------------------------\n";
    std::cout << "  TICK PROCESSING RESULTS:\n";
    std::cout << "  - Total Time:         " << (duration_tick_ns / 1'000'000.0) << " ms\n";
    std::cout << "  - Latency Per Tick:   " << ns_per_tick << " nanoseconds\n";
    std::cout << "  - Throughput:         " << (ticks_per_sec / 1'000'000.0) << " MILLION ticks / sec\n";
    std::cout << "========================================================\n";

    return 0;
}
