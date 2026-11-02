#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Input;
using System.Windows.Media;
using System.Xml.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Gui.SuperDom;
using NinjaTrader.Gui.Tools;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.Core.FloatingPoint;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.DrawingTools;
#endregion

namespace NinjaTrader.NinjaScript.Strategies
{
    /// <summary>
    /// Pure RTH 50% Equilibrium Institutional Execution Engine
    /// Canonical Morning Sniper Model (Option B Stoprun Continuation + 3-Loss Circuit Breaker)
    /// Direct 1-to-1 C# Implementation of canonical_variant_a.py (65.08% Win Rate, +$927k PnL)
    /// </summary>
    public class PureRTHEquilibriumStrategy : Strategy
    {
        private static readonly TimeZoneInfo EasternZone;

        static PureRTHEquilibriumStrategy()
        {
            try
            {
                EasternZone = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
            }
            catch
            {
                try
                {
                    EasternZone = TimeZoneInfo.FindSystemTimeZoneById("America/New_York");
                }
                catch
                {
                    EasternZone = TimeZoneInfo.Local;
                }
            }
        }

        private DateTime currentSessionDate = DateTime.MinValue;
        private bool isSessionInitializedToday = false;
        private string lastProcessedExitOrderId = string.Empty;
        private bool orderEntryPending = false;
        private MarketPosition currentOpenPosition = MarketPosition.Flat;

        private double dayHigh;
        private double dayLow;
        private int bullState;
        private double bullAnchor;
        private double bullExtreme;
        private double bullLowestW1;
        private double bullRetraceLow;
        private double bullStoprunLow;

        private int bearState;
        private double bearAnchor;
        private double bearExtreme;
        private double bearHighestW1;
        private double bearRetraceHigh;
        private double bearStoprunHigh;

        private string activeBias;
        private double trade50Level;
        private double entryPrice;
        private double currentSl;
        private double currentTp;
        private double lowestInTrade;
        private double highestInTrade;
        private int entryBarIndex = -1;
        private int lastExitBarIndex = -1;
        private int consecutiveLossCount;
        private bool dayHalted;

        // ==========================================
        // CANONICAL SYSTEM PARAMETERS
        // ==========================================
        [NinjaScriptProperty]
        [Range(1, 100)]
        [Display(Name="Quantity (Contracts)", Description="Number of micro contracts to trade (Canonical: 5 MNQ = $10/pt)", Order=1, GroupName="Parameters")]
        public int Contracts { get; set; }

        [NinjaScriptProperty]
        [Range(4, 400)]
        [Display(Name="Min Setup Range (Ticks)", Description="Minimum wave expansion range in ticks (Canonical: 32 ticks = 8.0 points)", Order=2, GroupName="Parameters")]
        public int MinSetupRangeTicks { get; set; }

        [NinjaScriptProperty]
        [Range(0, 100)]
        [Display(Name="Max Consecutive Losses", Description="Daily circuit breaker limit (0 = Disabled / No limit; 3 = Canonical stop)", Order=3, GroupName="Parameters")]
        public int MaxConsecutiveLosses { get; set; }

        [NinjaScriptProperty]
        [Display(Name="Live Market Orders", Description="In Realtime: true = Market order on touch; false = Limit order at 50%. (Historical simulation automatically fills at 50% limit)", Order=4, GroupName="Parameters")]
        public bool LiveMarketOrders { get; set; }

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description                                 = @"Pure RTH 50% Equilibrium Institutional Execution Engine (The Morning Sniper Option B)";
                Name                                        = "PureRTHEquilibriumStrategy";
                Calculate                                   = Calculate.OnPriceChange; // Instant intra-bar execution on 50% touch
                EntriesPerDirection                         = 1;
                EntryHandling                               = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy                = true;
                ExitOnSessionCloseSeconds                   = 60;
                IsFillLimitOnTouch                          = false;
                MaximumBarsLookBack                         = MaximumBarsLookBack.TwoHundredFiftySix;
                OrderFillResolution                         = OrderFillResolution.Standard;
                Slippage                                    = 0;
                StartBehavior                               = StartBehavior.WaitUntilFlat;
                TimeInForce                                 = TimeInForce.Gtc;
                TraceOrders                                 = false;
                RealtimeErrorHandling                       = RealtimeErrorHandling.StopCancelClose;
                StopTargetHandling                          = StopTargetHandling.PerEntryExecution;
                BarsRequiredToTrade                         = 1;

                // Pure Canonical Defaults (Unchanged from canonical_variant_a.py)
                Contracts                                   = 5;     // 5 MNQ contracts ($10/pt)
                MinSetupRangeTicks                          = 32;    // 32 ticks = 8.0 points minimum range
                MaxConsecutiveLosses                        = 3;     // 3 = Canonical 3-consecutive-loss daily stop
                LiveMarketOrders                            = true;  // Immediate fill on live 50% touch
            }
            else if (State == State.Configure)
            {
                ClearState();
            }
        }

        private DateTime GetEasternTime(DateTime barTime)
        {
            try
            {
                return TimeZoneInfo.ConvertTime(barTime, Core.Globals.GeneralOptions.TimeZoneInfo, EasternZone);
            }
            catch
            {
                return barTime;
            }
        }

        private void ClearState()
        {
            dayHigh = 0;
            dayLow = double.MaxValue;
            bullState = 0;
            bearState = 0;
            bullRetraceLow = 0;
            bullStoprunLow = 0;
            bearRetraceHigh = 0;
            bearStoprunHigh = 0;
            activeBias = null;
            orderEntryPending = false;
            lastExitBarIndex = -1;
            if (Position.MarketPosition == MarketPosition.Flat)
            {
                lowestInTrade = 0;
                highestInTrade = 0;
                entryBarIndex = -1;
                currentOpenPosition = MarketPosition.Flat;
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < BarsRequiredToTrade)
                return;

            DateTime easternNow = (State == State.Realtime) 
                ? TimeZoneInfo.ConvertTimeFromUtc(DateTime.UtcNow, EasternZone)
                : GetEasternTime(Time[0]);

            int time = ToTime(easternNow);

            // 1. HARD FLATTEN AT 11:30 AM EST SHARP (Canonical Morning Sniper Window)
            if (time >= 113000)
            {
                if (Position.MarketPosition != MarketPosition.Flat)
                {
                    if (Position.MarketPosition == MarketPosition.Long)
                        ExitLong("Flatten_1130");
                    else if (Position.MarketPosition == MarketPosition.Short)
                        ExitShort("Flatten_1130");
                }
                ClearState();
                return;
            }

            // Outside RTH (before 09:30 AM EST): Skip
            if (time < 093000)
                return;

            // 2. 09:30 AM EST FRESH SLATE RESET (NYSE Opening Bell)
            if (easternNow.Date != currentSessionDate || !isSessionInitializedToday)
            {
                currentSessionDate = easternNow.Date;
                isSessionInitializedToday = true;
                consecutiveLossCount = 0;
                dayHalted = false;
                dayHigh = High[0];
                dayLow = Low[0];
                bullState = 1;
                bullAnchor = dayLow;
                bullExtreme = dayLow;
                bullRetraceLow = dayLow;
                bullStoprunLow = dayLow;
                bearState = 1;
                bearAnchor = dayHigh;
                bearExtreme = dayHigh;
                bearRetraceHigh = dayHigh;
                bearStoprunHigh = dayHigh;
                activeBias = null;
                lowestInTrade = 0;
                highestInTrade = 0;
                entryBarIndex = -1;
                orderEntryPending = false;
                return;
            }

            // Track lowest and highest prices reached during an open trade
            if (Position.MarketPosition == MarketPosition.Long)
            {
                lowestInTrade = (lowestInTrade == 0) ? Low[0] : Math.Min(lowestInTrade, Low[0]);
            }
            else if (Position.MarketPosition == MarketPosition.Short)
            {
                highestInTrade = (highestInTrade == 0) ? High[0] : Math.Max(highestInTrade, High[0]);
            }

            // 3. CIRCUIT BREAKER CHECK
            bool isEntryAllowed = (time >= 093000 && time < 113000) && !dayHalted;

            // 4. SESSION HIGH / LOW TRACKING (Canonical Step 4)
            if (Low[0] < dayLow)
            {
                dayLow = Low[0];
                bullState = 1;
                bullAnchor = dayLow;
                bullExtreme = dayLow;
                if (activeBias == "BULL") activeBias = null;
            }

            if (High[0] > dayHigh)
            {
                dayHigh = High[0];
                bearState = 1;
                bearAnchor = dayHigh;
                bearExtreme = dayHigh;
                if (activeBias == "BEAR") activeBias = null;
            }

            double tick = TickSize;
            double minRange = MinSetupRangeTicks * tick; // Canonical: 32 ticks = 8.0 points

            // ==========================================
            // 5. BULLISH WAVE CYCLE (CANONICAL OPTION B)
            // ==========================================
            if (bullState == 1)
            {
                if (High[0] > bullExtreme) bullExtreme = High[0];
                double bull50 = bullExtreme - 0.50 * (bullExtreme - bullAnchor);
                if ((bullExtreme - bullAnchor) > tick && Low[0] <= bull50)
                {
                    bullState = 2;
                    bullLowestW1 = Low[0];
                }
            }
            else if (bullState == 2)
            {
                bullLowestW1 = Math.Min(bullLowestW1, Low[0]);
                if (Low[0] < bullAnchor)
                {
                    bullState = 0;
                    if (activeBias == "BULL") activeBias = null;
                }
                else if (High[0] >= bullExtreme)
                {
                    bullState = 3;
                    bullAnchor = bullLowestW1;
                    bullExtreme = High[0];
                    activeBias = "BULL"; // Recency Override
                }
            }
            else if (bullState == 3)
            {
                if (Low[0] < bullAnchor)
                {
                    if (Low[0] >= dayLow)
                    {
                        bullState = 5;
                        bullStoprunLow = Low[0];
                    }
                    else
                    {
                        bullState = 0;
                    }
                    if (activeBias == "BULL") activeBias = null;
                }
                else
                {
                    if (High[0] > bullExtreme) bullExtreme = High[0];
                    double bull50 = bullExtreme - 0.50 * (bullExtreme - bullAnchor);

                    // Touch Condition:
                    // In Realtime with Market Orders, live tick Close[0] must actively be at the 50% level (within 1 tick) to avoid chasing.
                    // In Historical backtest, candle Low[0] <= bull50 triggers the 50% limit fill.
                    bool isAt50Touch = (State == State.Realtime && LiveMarketOrders)
                        ? (Close[0] <= bull50 + tick)
                        : (Low[0] <= bull50);

                    if ((bullExtreme - bullAnchor) > tick && isAt50Touch)
                    {
                        bullState = 4;
                        bullRetraceLow = Low[0];
                        double tradeRange = bullExtreme - bullAnchor;

                        // Canonical Trade Execution Gate: Range >= 8.0 pts & Bias == BULL & Strict 1-Bar Separation
                        if (Position.MarketPosition == MarketPosition.Flat && !orderEntryPending && CurrentBar > lastExitBarIndex && isEntryAllowed && activeBias == "BULL" && tradeRange >= minRange)
                        {
                            trade50Level = bull50;
                            entryPrice = bull50;
                            double buffer = Close[0] * 0.00005; // Canonical micro-buffer
                            currentSl = bullAnchor - buffer;
                            currentTp = bullExtreme;
                            lowestInTrade = Low[0];
                            entryBarIndex = CurrentBar;
                            orderEntryPending = true;

                            SetStopLoss("50_Equilibrium_Long", CalculationMode.Price, currentSl, false);
                            SetProfitTarget("50_Equilibrium_Long", CalculationMode.Price, currentTp);

                            if (State == State.Realtime && LiveMarketOrders)
                                EnterLong(Contracts, "50_Equilibrium_Long");
                            else
                                EnterLongLimit(Contracts, entryPrice, "50_Equilibrium_Long");
                        }
                    }
                }
            }
            else if (bullState == 4)
            {
                bullRetraceLow = Math.Min(bullRetraceLow, Low[0]);
                if (Low[0] < bullAnchor)
                {
                    if (Low[0] >= dayLow)
                    {
                        bullState = 5;
                        bullStoprunLow = Low[0];
                    }
                    else
                    {
                        bullState = 0;
                    }
                    if (activeBias == "BULL") activeBias = null;
                }
                else if (High[0] >= bullExtreme)
                {
                    // Guard: Never evaluate on the entry bar itself to prevent premature anchor corruption
                    if (CurrentBar > entryBarIndex || Position.MarketPosition == MarketPosition.Flat)
                    {
                        bullState = 3;
                        bullAnchor = (lowestInTrade > 0) ? Math.Min(bullRetraceLow, lowestInTrade) : bullRetraceLow;
                        bullExtreme = High[0];
                        activeBias = "BULL";
                    }
                }
            }
            else if (bullState == 5)
            {
                // Option B: Wave Failure Stoprun Continuation
                bullStoprunLow = Math.Min(bullStoprunLow, Low[0]);
                if (High[0] >= bullExtreme)
                {
                    bullState = 3;
                    bullAnchor = bullStoprunLow;
                    bullExtreme = High[0];
                    activeBias = "BULL";
                }
            }

            // ==========================================
            // 6. BEARISH WAVE CYCLE (CANONICAL OPTION B)
            // ==========================================
            if (bearState == 1)
            {
                if (Low[0] < bearExtreme) bearExtreme = Low[0];
                double bear50 = bearExtreme + 0.50 * (bearAnchor - bearExtreme);
                if ((bearAnchor - bearExtreme) > tick && High[0] >= bear50)
                {
                    bearState = 2;
                    bearHighestW1 = High[0];
                }
            }
            else if (bearState == 2)
            {
                bearHighestW1 = Math.Max(bearHighestW1, High[0]);
                if (High[0] > bearAnchor)
                {
                    bearState = 0;
                    if (activeBias == "BEAR") activeBias = null;
                }
                else if (Low[0] <= bearExtreme)
                {
                    bearState = 3;
                    bearAnchor = bearHighestW1;
                    bearExtreme = Low[0];
                    activeBias = "BEAR"; // Recency Override
                }
            }
            else if (bearState == 3)
            {
                if (High[0] > bearAnchor)
                {
                    if (High[0] <= dayHigh)
                    {
                        bearState = 5;
                        bearStoprunHigh = High[0];
                    }
                    else
                    {
                        bearState = 0;
                    }
                    if (activeBias == "BEAR") activeBias = null;
                }
                else
                {
                    if (Low[0] < bearExtreme) bearExtreme = Low[0];
                    double bear50 = bearExtreme + 0.50 * (bearAnchor - bearExtreme);

                    // Touch Condition:
                    // In Realtime with Market Orders, live tick Close[0] must actively be at the 50% level (within 1 tick) to avoid chasing.
                    // In Historical backtest, candle High[0] >= bear50 triggers the 50% limit fill.
                    bool isAt50Touch = (State == State.Realtime && LiveMarketOrders)
                        ? (Close[0] >= bear50 - tick)
                        : (High[0] >= bear50);

                    if ((bearAnchor - bearExtreme) > tick && isAt50Touch)
                    {
                        bearState = 4;
                        bearRetraceHigh = High[0];
                        double tradeRange = bearAnchor - bearExtreme;

                        // Canonical Trade Execution Gate: Range >= 8.0 pts & Bias == BEAR & Strict 1-Bar Separation
                        if (Position.MarketPosition == MarketPosition.Flat && !orderEntryPending && CurrentBar > lastExitBarIndex && isEntryAllowed && activeBias == "BEAR" && tradeRange >= minRange)
                        {
                            trade50Level = bear50;
                            entryPrice = bear50;
                            double buffer = Close[0] * 0.00005; // Canonical micro-buffer
                            currentSl = bearAnchor + buffer;
                            currentTp = bearExtreme;
                            highestInTrade = High[0];
                            entryBarIndex = CurrentBar;
                            orderEntryPending = true;

                            SetStopLoss("50_Equilibrium_Short", CalculationMode.Price, currentSl, false);
                            SetProfitTarget("50_Equilibrium_Short", CalculationMode.Price, currentTp);

                            if (State == State.Realtime && LiveMarketOrders)
                                EnterShort(Contracts, "50_Equilibrium_Short");
                            else
                                EnterShortLimit(Contracts, entryPrice, "50_Equilibrium_Short");
                        }
                    }
                }
            }
            else if (bearState == 4)
            {
                bearRetraceHigh = Math.Max(bearRetraceHigh, High[0]);
                if (High[0] > bearAnchor)
                {
                    if (High[0] <= dayHigh)
                    {
                        bearState = 5;
                        bearStoprunHigh = High[0];
                    }
                    else
                    {
                        bearState = 0;
                    }
                    if (activeBias == "BEAR") activeBias = null;
                }
                else if (Low[0] <= bearExtreme)
                {
                    // Guard: Never evaluate on the entry bar itself to prevent premature anchor corruption
                    if (CurrentBar > entryBarIndex || Position.MarketPosition == MarketPosition.Flat)
                    {
                        bearState = 3;
                        bearAnchor = (highestInTrade > 0) ? Math.Max(bearRetraceHigh, highestInTrade) : bearRetraceHigh;
                        bearExtreme = Low[0];
                        activeBias = "BEAR";
                    }
                }
            }
            else if (bearState == 5)
            {
                // Option B: Wave Failure Stoprun Continuation
                bearStoprunHigh = Math.Max(bearStoprunHigh, High[0]);
                if (Low[0] <= bearExtreme)
                {
                    bearState = 3;
                    bearAnchor = bearStoprunHigh;
                    bearExtreme = Low[0];
                    activeBias = "BEAR";
                }
            }
        }

        protected override void OnOrderUpdate(Order order, double limitPrice, double stopPrice, int quantity, int filled, double averageFillPrice, OrderState orderState, DateTime time, ErrorCode error, string comment)
        {
            if (orderState == OrderState.Cancelled || orderState == OrderState.Rejected)
            {
                orderEntryPending = false;
            }
        }

        protected override void OnExecutionUpdate(Execution execution, string executionId, double price, int quantity, MarketPosition marketPosition, string orderId, DateTime time)
        {
            if (execution.Order != null && execution.Order.OrderState == OrderState.Filled)
            {
                orderEntryPending = false;

                // 1. Entry execution tracking: Record open position direction and execution fill price
                if (execution.Order.OrderAction == OrderAction.Buy)
                {
                    currentOpenPosition = MarketPosition.Long;
                    entryPrice = price;
                    return;
                }
                else if (execution.Order.OrderAction == OrderAction.SellShort)
                {
                    currentOpenPosition = MarketPosition.Short;
                    entryPrice = price;
                    return;
                }

                // 2. Exit execution: When position becomes Flat
                if (Position.MarketPosition == MarketPosition.Flat)
                {
                    entryBarIndex = -1;
                    lastExitBarIndex = CurrentBar;

                    if (execution.Order.OrderId == lastProcessedExitOrderId)
                        return;

                    lastProcessedExitOrderId = execution.Order.OrderId;

                    MarketPosition closedDirection = currentOpenPosition;
                    // Fallback to order action or name if currentOpenPosition was somehow flat
                    if (closedDirection == MarketPosition.Flat)
                    {
                        if (execution.Order.OrderAction == OrderAction.Sell || execution.Order.Name.Contains("Long"))
                            closedDirection = MarketPosition.Long;
                        else if (execution.Order.OrderAction == OrderAction.BuyToCover || execution.Order.Name.Contains("Short"))
                            closedDirection = MarketPosition.Short;
                    }

                    // Calculate realized points
                    double realizedPts = (closedDirection == MarketPosition.Long)
                        ? (price - entryPrice)
                        : (entryPrice - price);

                    // Win/Loss detection: Check Profit Target order name or realized points
                    bool isWin = (execution.Order != null && execution.Order.Name.Contains("Profit target")) || realizedPts > 0;

                    if (!isWin)
                    {
                        consecutiveLossCount++;
                        if (MaxConsecutiveLosses > 0 && consecutiveLossCount >= MaxConsecutiveLosses)
                        {
                            dayHalted = true;
                            Print(string.Format("{0} EST - Circuit Breaker Tripped: {1} consecutive losses reached today. Halting trading until tomorrow 09:30 AM EST.", GetEasternTime(Time[0]), consecutiveLossCount));
                        }

                        // Canonical SL Exit: Option B (State 5) or Reset (State 0)
                        if (closedDirection == MarketPosition.Long)
                        {
                            double exitLow = (lowestInTrade > 0) ? lowestInTrade : price;
                            if (exitLow >= dayLow)
                            {
                                bullState = 5;
                                bullStoprunLow = exitLow;
                            }
                            else
                            {
                                bullState = 0;
                            }
                            // Seamless bias transition: If opposing bearish wave has confirmed, preserve BEAR bias
                            activeBias = (bearState >= 3) ? "BEAR" : null;
                        }
                        else if (closedDirection == MarketPosition.Short)
                        {
                            double exitHigh = (highestInTrade > 0) ? highestInTrade : price;
                            if (exitHigh <= dayHigh)
                            {
                                bearState = 5;
                                bearStoprunHigh = exitHigh;
                            }
                            else
                            {
                                bearState = 0;
                            }
                            // Seamless bias transition: If opposing bullish wave has confirmed, preserve BULL bias
                            activeBias = (bullState >= 3) ? "BULL" : null;
                        }
                    }
                    else
                    {
                        consecutiveLossCount = 0;

                        // Canonical TP Exit: Anchor Next Wave immediately (State 3)
                        if (closedDirection == MarketPosition.Long)
                        {
                            bullAnchor = (lowestInTrade > 0) ? lowestInTrade : bullRetraceLow;
                            bullExtreme = currentTp;
                            activeBias = "BULL";
                            bullState = 3;
                        }
                        else if (closedDirection == MarketPosition.Short)
                        {
                            bearAnchor = (highestInTrade > 0) ? highestInTrade : bearRetraceHigh;
                            bearExtreme = currentTp;
                            activeBias = "BEAR";
                            bearState = 3;
                        }
                    }

                    currentOpenPosition = MarketPosition.Flat;
                    lowestInTrade = 0;
                    highestInTrade = 0;
                }
            }
        }
    }
}
