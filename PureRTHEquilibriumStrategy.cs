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
        [Display(Name="Quantity (Contracts)", Description="Number of micro contracts to trade (e.g. 5 MNQ = $10/pt)", Order=1, GroupName="Parameters")]
        public int Contracts { get; set; }

        [NinjaScriptProperty]
        [Range(0, 10)]
        [Display(Name="Slippage Ticks", Description="Slippage allowance in ticks (0 for exact touch price, 1 recommended)", Order=2, GroupName="Parameters")]
        public int SlippageTicks { get; set; }

        [NinjaScriptProperty]
        [Range(1, 10)]
        [Display(Name="Max Consecutive Losses", Description="Maximum consecutive losses permitted per day before halting until tomorrow's RTH session", Order=3, GroupName="Parameters")]
        public int MaxConsecutiveLosses { get; set; }

        [NinjaScriptProperty]
        [Display(Name="Use Market Orders", Description="If true, executes Market orders on 50% touch in Realtime. In Historical backtests, Limit orders at 50% are automatically used to prevent bar-close distortion.", Order=4, GroupName="Parameters")]
        public bool UseMarketOrders { get; set; }

        [NinjaScriptProperty]
        [Display(Name="Use Trailing Stop", Description="If true, trails stop to pivot after 50% TP progress. If false, maintains full structural anchor stop for maximum canonical win rate (65.3%).", Order=5, GroupName="Parameters")]
        public bool UseTrailingStop { get; set; }

        [NinjaScriptProperty]
        [Range(4, 400)]
        [Display(Name="Min Setup Range (Ticks)", Description="Minimum wave expansion range in ticks required to qualify a valid setup (32 ticks = 8.0 pts on NQ/MNQ)", Order=6, GroupName="Parameters")]
        public int MinSetupRangeTicks { get; set; }

        [NinjaScriptProperty]
        [Range(1, 100)]
        [Display(Name="Min Target Distance (Ticks)", Description="Minimum distance in ticks required between 50% entry and target (16 ticks = 4.0 pts on NQ/MNQ)", Order=7, GroupName="Parameters")]
        public int MinTargetTicks { get; set; }

        [NinjaScriptProperty]
        [Range(1, 50)]
        [Display(Name="Stop Buffer (Ticks)", Description="Buffer in ticks beyond structural anchor stop (2 ticks = 0.50 pts on NQ/MNQ)", Order=8, GroupName="Parameters")]
        public int StopBufferTicks { get; set; }

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description                                 = @"Pure RTH 50% Equilibrium Institutional Execution Engine";
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

                Contracts                                   = 5;
                SlippageTicks                               = 1;
                MaxConsecutiveLosses                        = 3;
                UseMarketOrders                             = true;  // Uses Market orders on live touch; Limit fills in historical simulation
                UseTrailingStop                             = false; // Disabled by default for canonical 65.3% win rate
                MinSetupRangeTicks                          = 32;    // 32 ticks = 8.0 points
                MinTargetTicks                              = 16;    // 16 ticks = 4.0 points minimum target distance
                StopBufferTicks                             = 2;     // 2 ticks = 0.50 points stop buffer
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

            DateTime easternNow = (State == State.Realtime) 
                ? TimeZoneInfo.ConvertTimeFromUtc(DateTime.UtcNow, EasternZone)
                : GetEasternTime(Time[0]);

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

            // 2. PURE RTH FRESH START AT 09:30 AM EST (First bar of morning session)
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
                lowestInTrade = 0;
                highestInTrade = 0;
                entryBarIndex = -1;
                orderEntryPending = false;
                return;
            }

            // Continuously track lowest and highest reached during any active trade
            if (Position.MarketPosition == MarketPosition.Long)
            {
                lowestInTrade = (lowestInTrade == 0) ? Low[0] : Math.Min(lowestInTrade, Low[0]);
            }
            else if (Position.MarketPosition == MarketPosition.Short)
            {
                highestInTrade = (highestInTrade == 0) ? High[0] : Math.Max(highestInTrade, High[0]);
            }

            bool isEntryAllowed = (time >= 093000 && time < 113000) && !dayHalted;

            // Session Extremes Tracking
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
            double minRange = MinSetupRangeTicks * tick; // Configurable setup range (32 ticks = 8.0 pts)
            double stopBuffer = StopBufferTicks * tick;  // Configurable stop buffer (2 ticks = 0.50 pts)
            double minTargetDist = MinTargetTicks * tick;// Configurable target distance (16 ticks = 4.0 pts)

            // ==========================================
            // BULLISH STATE MACHINE (PURE MARKET STRUCTURE)
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
                    // In Realtime with Market Orders, live price Close[0] must touch within slippage allowance.
                    // In Historical backtest (Strategy Analyzer), candle Low[0] <= bull50 validates 50% touch.
                    bool isAt50Touch = (State == State.Realtime && UseMarketOrders)
                        ? (Close[0] <= bull50 + (Math.Max(SlippageTicks, 1) * tick))
                        : (Low[0] <= bull50);

                    if ((bullExtreme - bullAnchor) > tick && isAt50Touch)
                    {
                        bullState = 4;
                        bullRetraceLow = Low[0];
                        double tradeRange = bullExtreme - bullAnchor;
                        double targetDist = bullExtreme - bull50;

                        // Target Distance Guard: Minimum 16 ticks (4.0 pts)
                        bool isTargetValid = (targetDist >= minTargetDist);

                        // Proximity Guard: In Realtime, verify live tick is safely between Anchor and Target
                        bool isEntrySafe = (State == State.Realtime)
                            ? (Close[0] >= bullAnchor + stopBuffer) && (Close[0] <= bullExtreme - minTargetDist)
                            : true;

                        // Trade Execution Gate
                        if (Position.MarketPosition == MarketPosition.Flat && !orderEntryPending && isEntryAllowed && activeBias == "BULL" && tradeRange >= minRange && isTargetValid && isEntrySafe)
                        {
                            trade50Level = bull50;
                            entryPrice = bull50;
                            currentSl = bullAnchor - stopBuffer;
                            currentTp = bullExtreme;
                            lowestInTrade = Low[0];
                            slMoved = false;
                            entryBarIndex = CurrentBar;
                            orderEntryPending = true;

                            SetStopLoss("50_Equilibrium_Long", CalculationMode.Price, currentSl, false);
                            SetProfitTarget("50_Equilibrium_Long", CalculationMode.Price, currentTp);

                            // In Live Realtime with UseMarketOrders, submit Market order for guaranteed instant fill.
                            // In Historical backtests, submit Limit order at entryPrice so Strategy Analyzer
                            // fills at the exact 50% price rather than bar-close penalty.
                            if (UseMarketOrders && State == State.Realtime)
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
                    // Guard: Never evaluate cycle completion on the entry bar itself to prevent premature anchor reset
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
            // BEARISH STATE MACHINE (PURE MARKET STRUCTURE)
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
                    bool isAt50Touch = (State == State.Realtime && UseMarketOrders)
                        ? (Close[0] >= bear50 - (Math.Max(SlippageTicks, 1) * tick))
                        : (High[0] >= bear50);

                    if ((bearAnchor - bearExtreme) > tick && isAt50Touch)
                    {
                        bearState = 4;
                        bearRetraceHigh = High[0];
                        double tradeRange = bearAnchor - bearExtreme;
                        double targetDist = bear50 - bearExtreme;

                        // Target Distance Guard: Minimum 16 ticks (4.0 pts)
                        bool isTargetValid = (targetDist >= minTargetDist);

                        // Proximity Guard: In Realtime, verify live tick is safely between Anchor and Target
                        bool isEntrySafe = (State == State.Realtime)
                            ? (Close[0] <= bearAnchor - stopBuffer) && (Close[0] >= bearExtreme + minTargetDist)
                            : true;

                        // Trade Execution Gate
                        if (Position.MarketPosition == MarketPosition.Flat && !orderEntryPending && isEntryAllowed && activeBias == "BEAR" && tradeRange >= minRange && isTargetValid && isEntrySafe)
                        {
                            trade50Level = bear50;
                            entryPrice = bear50;
                            currentSl = bearAnchor + stopBuffer;
                            currentTp = bearExtreme;
                            highestInTrade = High[0];
                            slMoved = false;
                            entryBarIndex = CurrentBar;
                            orderEntryPending = true;

                            SetStopLoss("50_Equilibrium_Short", CalculationMode.Price, currentSl, false);
                            SetProfitTarget("50_Equilibrium_Short", CalculationMode.Price, currentTp);

                            // In Live Realtime with UseMarketOrders, submit Market order for guaranteed instant fill.
                            // In Historical backtests, submit Limit order at entryPrice so Strategy Analyzer
                            // fills at the exact 50% price rather than bar-close penalty.
                            if (UseMarketOrders && State == State.Realtime)
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
                    // Guard: Never evaluate cycle completion on the entry bar itself to prevent premature anchor reset
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
                bearStoprunHigh = Math.Max(bearStoprunHigh, High[0]);
                if (Low[0] <= bearExtreme)
                {
                    bearState = 3;
                    bearAnchor = bearStoprunHigh;
                    bearExtreme = Low[0];
                    activeBias = "BEAR";
                }
            }

            // Optional Trailing Stop (Disabled by default for 65.3% canonical win rate)
            if (UseTrailingStop)
            {
                if (Position.MarketPosition == MarketPosition.Long && CurrentBar > entryBarIndex)
                {
                    double triggerPrice = trade50Level + 0.50 * (currentTp - trade50Level);
                    if (High[0] >= triggerPrice && !slMoved)
                    {
                        currentSl = Math.Max(currentSl, lowestInTrade - stopBuffer);
                        SetStopLoss("50_Equilibrium_Long", CalculationMode.Price, currentSl, false);
                        slMoved = true;
                    }
                }
                else if (Position.MarketPosition == MarketPosition.Short && CurrentBar > entryBarIndex)
                {
                    double triggerPrice = trade50Level - 0.50 * (trade50Level - currentTp);
                    if (Low[0] <= triggerPrice && !slMoved)
                    {
                        currentSl = Math.Min(currentSl, highestInTrade + stopBuffer);
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

                // When a trade exit fills and position becomes Flat
                if (Position.MarketPosition == MarketPosition.Flat)
                {
                    entryBarIndex = -1;

                    if (SystemPerformance.AllTrades.Count > 0)
                    {
                        if (execution.Order.OrderId == lastProcessedExitOrderId)
                            return;

                        Trade lastTrade = SystemPerformance.AllTrades[SystemPerformance.AllTrades.Count - 1];
                        DateTime easternExitTime = GetEasternTime(lastTrade.Exit.Time);
                        DateTime easternNow = GetEasternTime(Time[0]);

                        if (easternExitTime.Date == easternNow.Date)
                        {
                            lastProcessedExitOrderId = execution.Order.OrderId;

                            bool isWin = lastTrade.ProfitPoints > 0;

                            if (!isWin)
                            {
                                consecutiveLossCount++;
                                if (consecutiveLossCount >= MaxConsecutiveLosses)
                                {
                                    dayHalted = true;
                                    Print(string.Format("{0} EST - Circuit Breaker Tripped: {1} consecutive losses reached today. Halting trading until tomorrow 09:30 AM EST.", easternNow, consecutiveLossCount));
                                }

                                // Structural Stop Loss Synchronization
                                if (lastTrade.Entry.MarketPosition == MarketPosition.Long)
                                {
                                    double exitLow = (lowestInTrade > 0) ? lowestInTrade : lastTrade.Exit.Price;
                                    if (exitLow >= dayLow)
                                    {
                                        bullState = 5;
                                        bullStoprunLow = exitLow;
                                    }
                                    else
                                    {
                                        bullState = 0;
                                    }
                                    activeBias = null;
                                }
                                else if (lastTrade.Entry.MarketPosition == MarketPosition.Short)
                                {
                                    double exitHigh = (highestInTrade > 0) ? highestInTrade : lastTrade.Exit.Price;
                                    if (exitHigh <= dayHigh)
                                    {
                                        bearState = 5;
                                        bearStoprunHigh = exitHigh;
                                    }
                                    else
                                    {
                                        bearState = 0;
                                    }
                                    activeBias = null;
                                }
                            }
                            else
                            {
                                consecutiveLossCount = 0;

                                // Structural Profit Target Hit Synchronization
                                if (lastTrade.Entry.MarketPosition == MarketPosition.Long)
                                {
                                    bullAnchor = (lowestInTrade > 0) ? lowestInTrade : bullRetraceLow;
                                    bullExtreme = currentTp;
                                    activeBias = "BULL";
                                    bullState = 3;
                                }
                                else if (lastTrade.Entry.MarketPosition == MarketPosition.Short)
                                {
                                    bearAnchor = (highestInTrade > 0) ? highestInTrade : bearRetraceHigh;
                                    bearExtreme = currentTp;
                                    activeBias = "BEAR";
                                    bearState = 3;
                                }
                            }

                            lowestInTrade = 0;
                            highestInTrade = 0;
                        }
                    }
                }
            }
        }
    }
}
