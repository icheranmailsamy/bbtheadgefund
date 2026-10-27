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
        private bool slMoved;
        private int entryBarIndex = -1;
        private int consecutiveLossCount;
        private bool dayHalted;

        [NinjaScriptProperty]
        [Range(1, 100)]
        [Display(Name="Quantity (Contracts)", Description="Number of micro contracts to trade", Order=1, GroupName="Parameters")]
        public int Contracts { get; set; }

        [NinjaScriptProperty]
        [Range(0, 10)]
        [Display(Name="Slippage Ticks", Description="Slippage allowance in ticks (0 for exact market filling price)", Order=2, GroupName="Parameters")]
        public int SlippageTicks { get; set; }

        [NinjaScriptProperty]
        [Range(1, 10)]
        [Display(Name="Max Consecutive Losses", Description="Maximum consecutive losses permitted per day before halting until the next RTH session", Order=3, GroupName="Parameters")]
        public int MaxConsecutiveLosses { get; set; }

        [NinjaScriptProperty]
        [Display(Name="Use Market Orders", Description="If true, enters with Market orders on touch. If false, submits Limit orders at 50% + slippage ticks.", Order=4, GroupName="Parameters")]
        public bool UseMarketOrders { get; set; }

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description                                 = @"Pure RTH 50% Equilibrium Institutional Execution Engine";
                Name                                        = "PureRTHEquilibriumStrategy";
                Calculate                                   = Calculate.OnPriceChange; // Instant intra-bar entry on 50% touch (Zero waiting for bar close)
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

                Contracts                                   = 5;
                SlippageTicks                               = 0; // Exact market filling price
                MaxConsecutiveLosses                        = 3;
                UseMarketOrders                             = true; // Default to Market orders for guaranteed instant fills on 50% touch
            }
            else if (State == State.Configure)
            {
                // Clear any overnight state
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
            slMoved = false;
            lowestInTrade = 0;
            highestInTrade = 0;
            entryBarIndex = -1;
            orderEntryPending = false;
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < BarsRequiredToTrade)
                return;

            DateTime easternNow = GetEasternTime(Time[0]);
            int time = ToTime(easternNow);

            // 1. HARD FLATTEN AT 11:30 AM EST SHARP (The Morning Sniper Final Model)
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

            // Skip pre-market bars before 09:30 AM EST
            if (time < 093000)
                return;

            // 2. PURE RTH FRESH START AT 09:30 AM EST (First bar of today's morning sniper session)
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
                slMoved = false;
                return;
            }

            bool isEntryAllowed = (time >= 093000 && time < 113000) && !dayHalted;

            // Update session extremes
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

            double minRange = 8.0; // 8.0 points = 32 ticks minimum setup range (trade gate only)
            double tick = TickSize;

            // Bullish State Machine (Pure Market Structure)
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
                // Wave 2+ Expansion Phase: tracking peak
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

                    if ((bullExtreme - bullAnchor) > tick && Low[0] <= bull50)
                    {
                        bullState = 4;
                        bullRetraceLow = Low[0];
                        double tradeRange = bullExtreme - bullAnchor;

                        // Trade Execution Gate: Morning Sniper (09:30 - 11:30 EST)
                        if (Position.MarketPosition == MarketPosition.Flat && !orderEntryPending && isEntryAllowed && activeBias == "BULL" && tradeRange >= minRange)
                        {
                            trade50Level = bull50;
                            entryPrice = bull50 + (SlippageTicks * tick);
                            currentSl = bullAnchor - (Close[0] * 0.00005);
                            currentTp = bullExtreme;
                            lowestInTrade = Low[0];
                            slMoved = false;
                            entryBarIndex = CurrentBar;
                            orderEntryPending = true;

                            // Protection orders MUST be set before submitting entry order
                            SetStopLoss("50_Equilibrium_Long", CalculationMode.Price, currentSl, false);
                            SetProfitTarget("50_Equilibrium_Long", CalculationMode.Price, currentTp);

                            if (UseMarketOrders)
                                EnterLong(Contracts, "50_Equilibrium_Long");
                            else
                                EnterLongLimit(Contracts, entryPrice, "50_Equilibrium_Long");
                        }
                    }
                }
            }
            else if (bullState == 4)
            {
                // Wave 2+ Retracement Phase: tracking pullback low
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
                    // Cycle Completed! Move and start measuring next wave regardless of trade
                    bullState = 3;
                    bullAnchor = (lowestInTrade > 0) ? Math.Min(bullRetraceLow, lowestInTrade) : bullRetraceLow;
                    bullExtreme = High[0];
                    activeBias = "BULL";
                }
            }
            else if (bullState == 5)
            {
                // Option B: Stoprun Continuation Tracking
                bullStoprunLow = Math.Min(bullStoprunLow, Low[0]);
                if (High[0] >= bullExtreme)
                {
                    bullState = 3;
                    bullAnchor = bullStoprunLow;
                    bullExtreme = High[0];
                    activeBias = "BULL";
                }
            }

            // Bearish State Machine (Pure Market Structure)
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
                // Wave 2+ Expansion Phase: tracking valley
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

                    if ((bearAnchor - bearExtreme) > tick && High[0] >= bear50)
                    {
                        bearState = 4;
                        bearRetraceHigh = High[0];
                        double tradeRange = bearAnchor - bearExtreme;

                        // Trade Execution Gate: Morning Sniper (09:30 - 11:30 EST)
                        if (Position.MarketPosition == MarketPosition.Flat && !orderEntryPending && isEntryAllowed && activeBias == "BEAR" && tradeRange >= minRange)
                        {
                            trade50Level = bear50;
                            entryPrice = bear50 - (SlippageTicks * tick);
                            currentSl = bearAnchor + (Close[0] * 0.00005);
                            currentTp = bearExtreme;
                            highestInTrade = High[0];
                            slMoved = false;
                            entryBarIndex = CurrentBar;
                            orderEntryPending = true;

                            // Protection orders MUST be set before submitting entry order
                            SetStopLoss("50_Equilibrium_Short", CalculationMode.Price, currentSl, false);
                            SetProfitTarget("50_Equilibrium_Short", CalculationMode.Price, currentTp);

                            if (UseMarketOrders)
                                EnterShort(Contracts, "50_Equilibrium_Short");
                            else
                                EnterShortLimit(Contracts, entryPrice, "50_Equilibrium_Short");
                        }
                    }
                }
            }
            else if (bearState == 4)
            {
                // Wave 2+ Retracement Phase: tracking pullback high
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
                    // Cycle Completed! Move and start measuring next wave regardless of trade
                    bearState = 3;
                    bearAnchor = (highestInTrade > 0) ? Math.Max(bearRetraceHigh, highestInTrade) : bearRetraceHigh;
                    bearExtreme = Low[0];
                    activeBias = "BEAR";
                }
            }
            else if (bearState == 5)
            {
                // Option B: Stoprun Continuation Tracking
                bearStoprunHigh = Math.Max(bearStoprunHigh, High[0]);
                if (Low[0] <= bearExtreme)
                {
                    bearState = 3;
                    bearAnchor = bearStoprunHigh;
                    bearExtreme = Low[0];
                    activeBias = "BEAR";
                }
            }

            // Dynamic Risk Reduction Trailing Stop (Forward-bar evaluation matching canonical engine i+1 onwards)
            if (Position.MarketPosition == MarketPosition.Long)
            {
                lowestInTrade = Math.Min(lowestInTrade, Low[0]);

                // Crucial Guard: Only evaluate trailing stop on bars AFTER the entry bar.
                // In OnPriceChange mode, High[0] on the entry bar was formed before the pullback to 50%,
                // which would falsely satisfy triggerPrice immediately on the next tick and cause premature exit.
                if (CurrentBar > entryBarIndex)
                {
                    double triggerPrice = trade50Level + 0.50 * (currentTp - trade50Level);

                    if (High[0] >= triggerPrice && !slMoved)
                    {
                        currentSl = Math.Max(currentSl, lowestInTrade - (Close[0] * 0.00005));
                        SetStopLoss("50_Equilibrium_Long", CalculationMode.Price, currentSl, false);
                        slMoved = true;
                    }
                }
            }
            else if (Position.MarketPosition == MarketPosition.Short)
            {
                highestInTrade = Math.Max(highestInTrade, High[0]);

                // Crucial Guard: Only evaluate trailing stop on bars AFTER the entry bar.
                // In OnPriceChange mode, Low[0] on the entry bar was formed before the bounce to 50%,
                // which would falsely satisfy triggerPrice immediately on the next tick and cause premature exit.
                if (CurrentBar > entryBarIndex)
                {
                    double triggerPrice = trade50Level - 0.50 * (trade50Level - currentTp);

                    if (Low[0] <= triggerPrice && !slMoved)
                    {
                        currentSl = Math.Min(currentSl, highestInTrade + (Close[0] * 0.00005));
                        SetStopLoss("50_Equilibrium_Short", CalculationMode.Price, currentSl, false);
                        slMoved = true;
                    }
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

                // When a trade is closed and position is flat
                if (Position.MarketPosition == MarketPosition.Flat)
                {
                    entryBarIndex = -1;

                    if (SystemPerformance.AllTrades.Count > 0)
                    {
                        // Deduplicate multi-execution partial fills on the same exit order
                        if (execution.Order.OrderId == lastProcessedExitOrderId)
                            return;

                        Trade lastTrade = SystemPerformance.AllTrades[SystemPerformance.AllTrades.Count - 1];
                        DateTime easternExitTime = GetEasternTime(lastTrade.Exit.Time);
                        DateTime easternNow = GetEasternTime(Time[0]);

                        // Only process trades closed during the current session
                        if (easternExitTime.Date == easternNow.Date)
                        {
                            lastProcessedExitOrderId = execution.Order.OrderId;

                            if (lastTrade.ProfitPoints <= 0)
                            {
                                consecutiveLossCount++;
                                if (consecutiveLossCount >= MaxConsecutiveLosses)
                                {
                                    dayHalted = true;
                                    Print(string.Format("{0} EST - Circuit Breaker Tripped: {1} consecutive losses reached today. Halting trading until tomorrow 09:30 AM EST.", easternNow, consecutiveLossCount));
                                }
                            }
                            else
                            {
                                consecutiveLossCount = 0;
                            }
                        }
                    }
                }
            }
        }
    }
}
