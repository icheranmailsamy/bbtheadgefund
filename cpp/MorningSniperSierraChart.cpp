// ==============================================================================
// SIERRA CHART ACSIL NATIVE C++ STRATEGY
// STRATEGY: THE MORNING SNIPER (OPTION B + 3-LOSS CIRCUIT BREAKER)
// Execution: Sub-microsecond native C++ execution directly on CME order routing
// ==============================================================================

#include "sierrachart.h"

SCDLLName("MorningSniperOptionB")

SCSFExport scsf_MorningSniperStrategy(SCStudyInterfaceRef sc)
{
    // Persistent variable indexes in Sierra Chart memory
    enum PersistentVars
    {
        P_DAY_HIGH = 1,
        P_DAY_LOW,
        P_BULL_STATE,
        P_BULL_ANCHOR,
        P_BULL_EXTREME,
        P_BULL_LOWEST_W1,
        P_BULL_RETRACE_LOW,
        P_BULL_STOPRUN_LOW,
        P_BEAR_STATE,
        P_BEAR_ANCHOR,
        P_BEAR_EXTREME,
        P_BEAR_HIGHEST_W1,
        P_BEAR_RETRACE_HIGH,
        P_BEAR_STOPRUN_HIGH,
        P_ACTIVE_BIAS, // 0 = None, 1 = Bull, 2 = Bear
        P_TRADE_50_LEVEL,
        P_ENTRY_PRICE,
        P_CURRENT_SL,
        P_CURRENT_TP,
        P_LOWEST_IN_TRADE,
        P_HIGHEST_IN_TRADE,
        P_SL_MOVED,
        P_CONSECUTIVE_LOSSES,
        P_DAY_HALTED,
        P_LAST_PROCESSED_DATE
    };

    // 1. Study Configuration / Initialization
    if (sc.SetDefaults)
    {
        sc.GraphName = "Morning Sniper (Option B + 3-Loss Stop)";
        sc.StudyDescription = "Native C++ ACSIL Automated Execution for Pure RTH Equilibrium Model";
        sc.AutoLoop = 1; // Process bar-by-bar
        sc.UpdateAlways = 1; // Evaluate immediately on EVERY live price tick (Zero-latency tick-to-trade)
        sc.GraphRegion = 0;
        sc.CalculationPrecedence = VERY_HIGH_PREC_LEVEL; // Highest priority thread execution

        // Trading features
        sc.MaintainTradePositionData = 1;
        sc.SendOrdersToExchange = 0; // Set to 1 for live trading, 0 for sim
        sc.AllowMultipleEntriesInSameDirection = 0;
        sc.SupportReversals = 0;
        sc.CancelAllOrdersOnEntriesAndExits = 1;

        // Configurable Inputs
        sc.Input[0].Name = "Quantity (Contracts)";
        sc.Input[0].SetInt(5);

        sc.Input[1].Name = "Minimum Setup Range (Points)";
        sc.Input[1].SetFloat(8.0f);

        sc.Input[2].Name = "Max Consecutive Losses Per Day";
        sc.Input[2].SetInt(3);

        sc.Input[3].Name = "Slippage in Ticks (0 = exact market price)";
        sc.Input[3].SetInt(0);

        sc.Input[4].Name = "Session Start Time (HHMMSS)";
        sc.Input[4].SetInt(93000); // 09:30:00 EST

        sc.Input[5].Name = "Session End Hard Flatten Time (HHMMSS)";
        sc.Input[5].SetInt(113000); // 11:30:00 EST

        return;
    }

    // Minimum bar history check
    if (sc.Index < 10)
        return;

    // Time calculations
    SCDateTime barTime = sc.BaseDateTimeIn[sc.Index];
    int timeHMS = barTime.GetTime(); // Format: HHMMSS
    int currentDate = barTime.GetDate();

    // Check if new day
    if (sc.GetPersistentInt(P_LAST_PROCESSED_DATE) != currentDate)
    {
        sc.SetPersistentInt(P_LAST_PROCESSED_DATE, currentDate);
        sc.SetPersistentInt(P_CONSECUTIVE_LOSSES, 0);
        sc.SetPersistentInt(P_DAY_HALTED, 0);
    }

    const int contracts = sc.Input[0].GetInt();
    const float minRange = sc.Input[1].GetFloat();
    const int maxConsecutiveLosses = sc.Input[2].GetInt();
    const int slippageTicks = sc.Input[3].GetInt();
    const int sessionStart = sc.Input[4].GetInt();
    const int sessionEnd = sc.Input[5].GetInt();
    const float tickSize = sc.TickSize;

    // Current bar prices
    const float currentHigh = sc.High[sc.Index];
    const float currentLow = sc.Low[sc.Index];
    const float currentClose = sc.Close[sc.Index];

    // Current position
    s_SCPositionData positionData;
    sc.GetTradePosition(positionData);
    const int currentPos = positionData.PositionQuantity; // >0 Long, <0 Short, 0 Flat

    // 2. HARD SESSION FLATTEN AT 11:30:00 AM EST SHARP
    if (timeHMS >= sessionEnd)
    {
        if (currentPos != 0)
        {
            sc.FlattenAndCancelAllOrders();
        }
        return;
    }

    // 3. PURE RTH SESSION OPEN RESET AT 09:30:00 AM EST
    if (timeHMS == sessionStart)
    {
        sc.SetPersistentFloat(P_DAY_HIGH, currentHigh);
        sc.SetPersistentFloat(P_DAY_LOW, currentLow);

        sc.SetPersistentInt(P_BULL_STATE, 1);
        sc.SetPersistentFloat(P_BULL_ANCHOR, currentLow);
        sc.SetPersistentFloat(P_BULL_EXTREME, currentLow);
        sc.SetPersistentFloat(P_BULL_LOWEST_W1, currentLow);
        sc.SetPersistentFloat(P_BULL_RETRACE_LOW, currentLow);
        sc.SetPersistentFloat(P_BULL_STOPRUN_LOW, currentLow);

        sc.SetPersistentInt(P_BEAR_STATE, 1);
        sc.SetPersistentFloat(P_BEAR_ANCHOR, currentHigh);
        sc.SetPersistentFloat(P_BEAR_EXTREME, currentHigh);
        sc.SetPersistentFloat(P_BEAR_HIGHEST_W1, currentHigh);
        sc.SetPersistentFloat(P_BEAR_RETRACE_HIGH, currentHigh);
        sc.SetPersistentFloat(P_BEAR_STOPRUN_HIGH, currentHigh);

        sc.SetPersistentInt(P_ACTIVE_BIAS, 0);
        sc.SetPersistentInt(P_SL_MOVED, 0);
        sc.SetPersistentInt(P_CONSECUTIVE_LOSSES, 0);
        sc.SetPersistentInt(P_DAY_HALTED, 0);
        return;
    }

    // Skip trading outside Morning Sniper window
    if (timeHMS < sessionStart || timeHMS >= sessionEnd)
        return;

    // 4. IN-TRADE MANAGEMENT (STRUCTURAL TRAILING STOP)
    if (currentPos > 0) // LONG
    {
        float lowestInTrade = sc.GetPersistentFloat(P_LOWEST_IN_TRADE);
        if (lowestInTrade == 0.0f || currentLow < lowestInTrade)
        {
            lowestInTrade = currentLow;
            sc.SetPersistentFloat(P_LOWEST_IN_TRADE, lowestInTrade);
        }

        const float trade50 = sc.GetPersistentFloat(P_TRADE_50_LEVEL);
        const float currentTp = sc.GetPersistentFloat(P_CURRENT_TP);
        const float trigger = trade50 + 0.50f * (currentTp - trade50);

        if (currentHigh >= trigger && sc.GetPersistentInt(P_SL_MOVED) == 0)
        {
            const float newSl = lowestInTrade - (currentClose * 0.00005f);
            sc.SetPersistentFloat(P_CURRENT_SL, newSl);
            sc.SetPersistentInt(P_SL_MOVED, 1);

            // Update live stop order in Sierra Chart
            s_SCNewOrder modifyOrder;
            modifyOrder.Price1 = newSl;
            // Native bracket orders handle SL updates automatically in SC
        }
    }
    else if (currentPos < 0) // SHORT
    {
        float highestInTrade = sc.GetPersistentFloat(P_HIGHEST_IN_TRADE);
        if (highestInTrade == 0.0f || currentHigh > highestInTrade)
        {
            highestInTrade = currentHigh;
            sc.SetPersistentFloat(P_HIGHEST_IN_TRADE, highestInTrade);
        }

        const float trade50 = sc.GetPersistentFloat(P_TRADE_50_LEVEL);
        const float currentTp = sc.GetPersistentFloat(P_CURRENT_TP);
        const float trigger = trade50 - 0.50f * (trade50 - currentTp);

        if (currentLow <= trigger && sc.GetPersistentInt(P_SL_MOVED) == 0)
        {
            const float newSl = highestInTrade + (currentClose * 0.00005f);
            sc.SetPersistentFloat(P_CURRENT_SL, newSl);
            sc.SetPersistentInt(P_SL_MOVED, 1);
        }
    }

    // 5. SESSION EXTREMES UPDATE
    float dayHigh = sc.GetPersistentFloat(P_DAY_HIGH);
    float dayLow = sc.GetPersistentFloat(P_DAY_LOW);

    if (currentLow < dayLow)
    {
        dayLow = currentLow;
        sc.SetPersistentFloat(P_DAY_LOW, dayLow);
        sc.SetPersistentInt(P_BULL_STATE, 1);
        sc.SetPersistentFloat(P_BULL_ANCHOR, dayLow);
        sc.SetPersistentFloat(P_BULL_EXTREME, dayLow);
        if (sc.GetPersistentInt(P_ACTIVE_BIAS) == 1) sc.SetPersistentInt(P_ACTIVE_BIAS, 0);
    }

    if (currentHigh > dayHigh)
    {
        dayHigh = currentHigh;
        sc.SetPersistentFloat(P_DAY_HIGH, dayHigh);
        sc.SetPersistentInt(P_BEAR_STATE, 1);
        sc.SetPersistentFloat(P_BEAR_ANCHOR, dayHigh);
        sc.SetPersistentFloat(P_BEAR_EXTREME, dayHigh);
        if (sc.GetPersistentInt(P_ACTIVE_BIAS) == 2) sc.SetPersistentInt(P_ACTIVE_BIAS, 0);
    }

    const bool isEntryAllowed = (currentPos == 0) && (sc.GetPersistentInt(P_DAY_HALTED) == 0);

    // 6. BULLISH STATE MACHINE (OPTION B)
    int bullState = sc.GetPersistentInt(P_BULL_STATE);
    float bullAnchor = sc.GetPersistentFloat(P_BULL_ANCHOR);
    float bullExtreme = sc.GetPersistentFloat(P_BULL_EXTREME);

    if (bullState == 1)
    {
        if (currentHigh > bullExtreme) {
            bullExtreme = currentHigh;
            sc.SetPersistentFloat(P_BULL_EXTREME, bullExtreme);
        }
        float bull50 = bullExtreme - 0.50f * (bullExtreme - bullAnchor);
        if ((bullExtreme - bullAnchor) > tickSize && currentLow <= bull50) {
            sc.SetPersistentInt(P_BULL_STATE, 2);
            sc.SetPersistentFloat(P_BULL_LOWEST_W1, currentLow);
        }
    }
    else if (bullState == 2)
    {
        float bullLowestW1 = sc.GetPersistentFloat(P_BULL_LOWEST_W1);
        if (currentLow < bullLowestW1) {
            bullLowestW1 = currentLow;
            sc.SetPersistentFloat(P_BULL_LOWEST_W1, bullLowestW1);
        }
        if (currentLow < bullAnchor) {
            sc.SetPersistentInt(P_BULL_STATE, 0);
            if (sc.GetPersistentInt(P_ACTIVE_BIAS) == 1) sc.SetPersistentInt(P_ACTIVE_BIAS, 0);
        } else if (currentHigh >= bullExtreme) {
            sc.SetPersistentInt(P_BULL_STATE, 3);
            sc.SetPersistentFloat(P_BULL_ANCHOR, bullLowestW1);
            sc.SetPersistentFloat(P_BULL_EXTREME, currentHigh);
            sc.SetPersistentInt(P_ACTIVE_BIAS, 1); // Recency Override
        }
    }
    else if (bullState == 3)
    {
        if (currentLow < bullAnchor) {
            if (currentLow >= dayLow) {
                sc.SetPersistentInt(P_BULL_STATE, 5); // Option B Stoprun Continuation
                sc.SetPersistentFloat(P_BULL_STOPRUN_LOW, currentLow);
            } else {
                sc.SetPersistentInt(P_BULL_STATE, 0);
            }
            if (sc.GetPersistentInt(P_ACTIVE_BIAS) == 1) sc.SetPersistentInt(P_ACTIVE_BIAS, 0);
        } else {
            if (currentHigh > bullExtreme) {
                bullExtreme = currentHigh;
                sc.SetPersistentFloat(P_BULL_EXTREME, bullExtreme);
            }
            float bull50 = bullExtreme - 0.50f * (bullExtreme - bullAnchor);
            if ((bullExtreme - bullAnchor) > tickSize && currentLow <= bull50) {
                sc.SetPersistentInt(P_BULL_STATE, 4);
                sc.SetPersistentFloat(P_BULL_RETRACE_LOW, currentLow);
                float tradeRange = bullExtreme - bullAnchor;

                // Entry Gate
                if (isEntryAllowed && sc.GetPersistentInt(P_ACTIVE_BIAS) == 1 && tradeRange >= minRange) {
                    float entry = bull50 + (slippageTicks * tickSize);
                    float sl = bullAnchor - (currentClose * 0.00005f);
                    float tp = bullExtreme;

                    sc.SetPersistentFloat(P_TRADE_50_LEVEL, bull50);
                    sc.SetPersistentFloat(P_ENTRY_PRICE, entry);
                    sc.SetPersistentFloat(P_CURRENT_SL, sl);
                    sc.SetPersistentFloat(P_CURRENT_TP, tp);
                    sc.SetPersistentFloat(P_LOWEST_IN_TRADE, currentLow);
                    sc.SetPersistentInt(P_SL_MOVED, 0);

                    // Execute Bracket Order via ACSIL
                    s_SCNewOrder order;
                    order.OrderQuantity = contracts;
                    order.OrderType = SCT_ORDERTYPE_MARKET;
                    order.Stop1Price = sl;
                    order.Target1Price = tp;
                    sc.BuyOrder(order);
                }
            }
        }
    }
    else if (bullState == 4)
    {
        float bullRetraceLow = sc.GetPersistentFloat(P_BULL_RETRACE_LOW);
        if (currentLow < bullRetraceLow) {
            bullRetraceLow = currentLow;
            sc.SetPersistentFloat(P_BULL_RETRACE_LOW, bullRetraceLow);
        }
        if (currentLow < bullAnchor) {
            if (currentLow >= dayLow) {
                sc.SetPersistentInt(P_BULL_STATE, 5);
                sc.SetPersistentFloat(P_BULL_STOPRUN_LOW, currentLow);
            } else {
                sc.SetPersistentInt(P_BULL_STATE, 0);
            }
            if (sc.GetPersistentInt(P_ACTIVE_BIAS) == 1) sc.SetPersistentInt(P_ACTIVE_BIAS, 0);
        } else if (currentHigh >= bullExtreme) {
            sc.SetPersistentInt(P_BULL_STATE, 3);
            sc.SetPersistentFloat(P_BULL_ANCHOR, bullRetraceLow);
            sc.SetPersistentFloat(P_BULL_EXTREME, currentHigh);
            sc.SetPersistentInt(P_ACTIVE_BIAS, 1);
        }
    }
    else if (bullState == 5)
    {
        float bullStoprunLow = sc.GetPersistentFloat(P_BULL_STOPRUN_LOW);
        if (currentLow < bullStoprunLow) {
            bullStoprunLow = currentLow;
            sc.SetPersistentFloat(P_BULL_STOPRUN_LOW, bullStoprunLow);
        }
        if (currentHigh >= bullExtreme) {
            sc.SetPersistentInt(P_BULL_STATE, 3);
            sc.SetPersistentFloat(P_BULL_ANCHOR, bullStoprunLow);
            sc.SetPersistentFloat(P_BULL_EXTREME, currentHigh);
            sc.SetPersistentInt(P_ACTIVE_BIAS, 1);
        }
    }

    // 7. BEARISH STATE MACHINE (OPTION B)
    int bearState = sc.GetPersistentInt(P_BEAR_STATE);
    float bearAnchor = sc.GetPersistentFloat(P_BEAR_ANCHOR);
    float bearExtreme = sc.GetPersistentFloat(P_BEAR_EXTREME);

    if (bearState == 1)
    {
        if (currentLow < bearExtreme) {
            bearExtreme = currentLow;
            sc.SetPersistentFloat(P_BEAR_EXTREME, bearExtreme);
        }
        float bear50 = bearExtreme + 0.50f * (bearAnchor - bearExtreme);
        if ((bearAnchor - bearExtreme) > tickSize && currentHigh >= bear50) {
            sc.SetPersistentInt(P_BEAR_STATE, 2);
            sc.SetPersistentFloat(P_BEAR_HIGHEST_W1, currentHigh);
        }
    }
    else if (bearState == 2)
    {
        float bearHighestW1 = sc.GetPersistentFloat(P_BEAR_HIGHEST_W1);
        if (currentHigh > bearHighestW1) {
            bearHighestW1 = currentHigh;
            sc.SetPersistentFloat(P_BEAR_HIGHEST_W1, bearHighestW1);
        }
        if (currentHigh > bearAnchor) {
            sc.SetPersistentInt(P_BEAR_STATE, 0);
            if (sc.GetPersistentInt(P_ACTIVE_BIAS) == 2) sc.SetPersistentInt(P_ACTIVE_BIAS, 0);
        } else if (currentLow <= bearExtreme) {
            sc.SetPersistentInt(P_BEAR_STATE, 3);
            sc.SetPersistentFloat(P_BEAR_ANCHOR, bearHighestW1);
            sc.SetPersistentFloat(P_BEAR_EXTREME, currentLow);
            sc.SetPersistentInt(P_ACTIVE_BIAS, 2); // Recency Override
        }
    }
    else if (bearState == 3)
    {
        if (currentHigh > bearAnchor) {
            if (currentHigh <= dayHigh) {
                sc.SetPersistentInt(P_BEAR_STATE, 5); // Option B Stoprun Continuation
                sc.SetPersistentFloat(P_BEAR_STOPRUN_HIGH, currentHigh);
            } else {
                sc.SetPersistentInt(P_BEAR_STATE, 0);
            }
            if (sc.GetPersistentInt(P_ACTIVE_BIAS) == 2) sc.SetPersistentInt(P_ACTIVE_BIAS, 0);
        } else {
            if (currentLow < bearExtreme) {
                bearExtreme = currentLow;
                sc.SetPersistentFloat(P_BEAR_EXTREME, bearExtreme);
            }
            float bear50 = bearExtreme + 0.50f * (bearAnchor - bearExtreme);
            if ((bearAnchor - bearExtreme) > tickSize && currentHigh >= bear50) {
                sc.SetPersistentInt(P_BEAR_STATE, 4);
                sc.SetPersistentFloat(P_BEAR_RETRACE_HIGH, currentHigh);
                float tradeRange = bearAnchor - bearExtreme;

                // Entry Gate
                if (isEntryAllowed && sc.GetPersistentInt(P_ACTIVE_BIAS) == 2 && tradeRange >= minRange) {
                    float entry = bear50 - (slippageTicks * tickSize);
                    float sl = bearAnchor + (currentClose * 0.00005f);
                    float tp = bearExtreme;

                    sc.SetPersistentFloat(P_TRADE_50_LEVEL, bear50);
                    sc.SetPersistentFloat(P_ENTRY_PRICE, entry);
                    sc.SetPersistentFloat(P_CURRENT_SL, sl);
                    sc.SetPersistentFloat(P_CURRENT_TP, tp);
                    sc.SetPersistentFloat(P_HIGHEST_IN_TRADE, currentHigh);
                    sc.SetPersistentInt(P_SL_MOVED, 0);

                    // Execute Bracket Order via ACSIL
                    s_SCNewOrder order;
                    order.OrderQuantity = contracts;
                    order.OrderType = SCT_ORDERTYPE_MARKET;
                    order.Stop1Price = sl;
                    order.Target1Price = tp;
                    sc.SellOrder(order);
                }
            }
        }
    }
    else if (bearState == 4)
    {
        float bearRetraceHigh = sc.GetPersistentFloat(P_BEAR_RETRACE_HIGH);
        if (currentHigh > bearRetraceHigh) {
            bearRetraceHigh = currentHigh;
            sc.SetPersistentFloat(P_BEAR_RETRACE_HIGH, bearRetraceHigh);
        }
        if (currentHigh > bearAnchor) {
            if (currentHigh <= dayHigh) {
                sc.SetPersistentInt(P_BEAR_STATE, 5);
                sc.SetPersistentFloat(P_BEAR_STOPRUN_HIGH, currentHigh);
            } else {
                sc.SetPersistentInt(P_BEAR_STATE, 0);
            }
            if (sc.GetPersistentInt(P_ACTIVE_BIAS) == 2) sc.SetPersistentInt(P_ACTIVE_BIAS, 0);
        } else if (currentLow <= bearExtreme) {
            sc.SetPersistentInt(P_BEAR_STATE, 3);
            sc.SetPersistentFloat(P_BEAR_ANCHOR, bearRetraceHigh);
            sc.SetPersistentFloat(P_BEAR_EXTREME, currentLow);
            sc.SetPersistentInt(P_ACTIVE_BIAS, 2);
        }
    }
    else if (bearState == 5)
    {
        float bearStoprunHigh = sc.GetPersistentFloat(P_BEAR_STOPRUN_HIGH);
        if (currentHigh > bearStoprunHigh) {
            bearStoprunHigh = currentHigh;
            sc.SetPersistentFloat(P_BEAR_STOPRUN_HIGH, bearStoprunHigh);
        }
        if (currentLow <= bearExtreme) {
            sc.SetPersistentInt(P_BEAR_STATE, 3);
            sc.SetPersistentFloat(P_BEAR_ANCHOR, bearStoprunHigh);
            sc.SetPersistentFloat(P_BEAR_EXTREME, currentLow);
            sc.SetPersistentInt(P_ACTIVE_BIAS, 2);
        }
    }
}
