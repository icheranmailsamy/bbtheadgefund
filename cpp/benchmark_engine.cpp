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

    // Generate 1,000,000 synthetic 1-minute bars
    const size_t NUM_BARS = 1'000'000;
    std::vector<QuantEngine::Bar> bars;
    bars.reserve(NUM_BARS);

    double current_price = 21000.0;
    int32_t current_time = 93000;

    std::mt19937_64 rng(42);
    std::normal_distribution<double> dist(0.0, 1.5);

    for (size_t i = 0; i < NUM_BARS; ++i) {
        QuantEngine::Bar b;
        b.timestamp_ms = 1700000000000LL + i * 60000LL;
        b.hhmmss = current_time;
        b.open = current_price;
        const double delta1 = dist(rng);
        const double delta2 = dist(rng);
        b.high = b.open + std::max({0.0, delta1, delta2});
        b.low = b.open + std::min({0.0, delta1, delta2});
        b.close = b.low + (b.high - b.low) * 0.5;
        b.volume = 100.0;

        bars.push_back(b);
        current_price = b.close;

        // Advance simulated time
        current_time += 100;
        if ((current_time % 10000) >= 6000) {
            current_time = current_time - 6000 + 10000;
        }
        if (current_time > 113000) {
            current_time = 93000; // Next session
        }
    }

    std::cout << "[BENCHMARK] Processing " << NUM_BARS << " 1-minute futures bars...\n";

    int64_t trade_count = 0;
    const auto t_start = std::chrono::high_resolution_clock::now();

    for (const auto& bar : bars) {
        auto sig = engine.process_bar(bar);
        if (sig.action != QuantEngine::OrderAction::NONE) {
            trade_count++;
        }
    }

    const auto t_end = std::chrono::high_resolution_clock::now();
    const auto duration_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(t_end - t_start).count();
    const double duration_ms = duration_ns / 1'000'000.0;
    const double ns_per_bar = static_cast<double>(duration_ns) / NUM_BARS;
    const double bars_per_sec = (static_cast<double>(NUM_BARS) / duration_ns) * 1e9;

    std::cout << std::fixed << std::setprecision(2);
    std::cout << "--------------------------------------------------------\n";
    std::cout << "  RESULTS:\n";
    std::cout << "  - Total Time:         " << duration_ms << " ms\n";
    std::cout << "  - Latency Per Bar:    " << ns_per_bar << " nanoseconds (" << (ns_per_bar / 1000.0) << " microseconds)\n";
    std::cout << "  - Throughput:         " << bars_per_sec << " bars / second\n";
    std::cout << "  - Signals Fired:      " << trade_count << "\n";
    std::cout << "========================================================\n";

    return 0;
}
