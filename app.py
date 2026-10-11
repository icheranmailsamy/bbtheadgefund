import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import datetime
import os

from engine.storage import (
    init_db, get_accounts, add_account, toggle_account_status,
    delete_account, get_trades_df, log_trade_record
)
from engine.strategy import PureRTHEquilibriumStrategyEngine
from engine.risk_engine import RiskManagementEngine
from engine.broker_router import BrokerMultiAccountRouter

st.set_page_config(
    page_title="Institutional Quant Terminal | 50% Equilibrium",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for high-end dark institutional aesthetic
st.markdown("""
<style>
    .main { background-color: #0d1117; color: #c9d1d9; }
    .stMetric { background-color: #161b22; border-radius: 8px; padding: 12px; border: 1px solid #30363d; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { background-color: #161b22; border-radius: 6px; padding: 8px 16px; color: #8b949e; }
    .stTabs [aria-selected="true"] { background-color: #238636 !important; color: white !important; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# Initialize Database
init_db()

# Session State for Live Strategy Simulator
if "strategy" not in st.session_state:
    st.session_state.strategy = PureRTHEquilibriumStrategyEngine(asset="MNQ")
if "risk" not in st.session_state:
    st.session_state.risk = RiskManagementEngine(asset="MNQ")
if "router" not in st.session_state:
    st.session_state.router = BrokerMultiAccountRouter(asset="MNQ")
if "current_bar_index" not in st.session_state:
    st.session_state.current_bar_index = 0
if "sim_price" not in st.session_state:
    st.session_state.sim_price = 18500.0

# ----------------- SIDEBAR -----------------
st.sidebar.title("⚡ 50% QUANT ENGINE")
st.sidebar.markdown("**Institutional Orderflow Terminal**")
st.sidebar.markdown("---")

accounts_df = get_accounts()
active_count = len(accounts_df[accounts_df['is_active'] == 1]) if not accounts_df.empty else 0

st.sidebar.metric("Target Asset", "MNQ (Micro NQ)")
st.sidebar.metric("Active API Accounts", f"{active_count} Connected")
st.sidebar.metric("Session Mode", "Pure RTH (09:30 - 15:55)")
st.sidebar.metric("Overnight Risk", "0.00% (Cash at 15:59)")

st.sidebar.markdown("---")
engine_active = st.sidebar.toggle("🟢 Master Engine Active", value=True)
if engine_active:
    st.sidebar.success("Engine: LISTENING TO FEED")
else:
    st.sidebar.warning("Engine: STOPPED")

st.sidebar.markdown("---")
st.sidebar.caption("Repo: `icheranmailsamy/bbtheadgefund`")

# ----------------- MAIN APP TABS -----------------
tab_dashboard, tab_engine, tab_accounts, tab_history = st.tabs([
    "📊 Quant Dashboard",
    "⚙️ Strategy & Signal Engine",
    "🔑 Multi-Account Manager",
    "📜 Trade History & Audit"
])

# ================= TAB 1: QUANT DASHBOARD =================
with tab_dashboard:
    st.subheader("Institutional Performance Dashboard")
    
    trades_df = get_trades_df()
    
    if trades_df.empty:
        st.info("No live trade executions logged yet. Connect an API account and let the engine trade, or trigger simulation trades in Tab 2.")
    else:
        # Account Filter
        account_list = ["ALL ACCOUNTS"] + trades_df['account_name'].unique().tolist()
        selected_acc = st.selectbox("Filter Analytics by Account:", account_list)
        
        df_filtered = trades_df.copy()
        if selected_acc != "ALL ACCOUNTS":
            df_filtered = df_filtered[df_filtered['account_name'] == selected_acc]
            
        df_filtered = df_filtered.sort_values(by='trade_time', ascending=True).reset_index(drop=True)
        df_filtered['cum_pnl'] = df_filtered['pnl_usd'].cumsum()
        df_filtered['peak'] = df_filtered['cum_pnl'].cummax()
        df_filtered['drawdown_usd'] = df_filtered['cum_pnl'] - df_filtered['peak']
        
        # Core Metrics
        total_profit = df_filtered['pnl_usd'].sum()
        total_trades = len(df_filtered)
        winning_trades = len(df_filtered[df_filtered['pnl_usd'] > 0])
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        gross_profit = df_filtered[df_filtered['pnl_usd'] > 0]['pnl_usd'].sum()
        gross_loss = abs(df_filtered[df_filtered['pnl_usd'] <= 0]['pnl_usd'].sum())
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (float('inf') if gross_profit > 0 else 0.0)
        max_dd = df_filtered['drawdown_usd'].min()
        
        # Row 1 KPIs
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Net Profit", f"${total_profit:,.2f}", delta=f"{win_rate:.1f}% WR")
        c2.metric("Profit Factor", f"{profit_factor:.2f}" if profit_factor != float('inf') else "∞")
        c3.metric("Max Drawdown ($)", f"${max_dd:,.2f}")
        c4.metric("Total Trades Executed", f"{total_trades:,}")
        
        # Row 2 Charts
        st.markdown("### Cumulative Equity Curve")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_filtered['trade_time'],
            y=df_filtered['cum_pnl'],
            mode='lines',
            name='Net Equity ($)',
            line=dict(color='#00FFAA', width=2.5),
            fill='tozeroy',
            fillcolor='rgba(0, 255, 170, 0.08)'
        ))
        fig.update_layout(
            template='plotly_dark',
            paper_bgcolor='#0d1117',
            plot_bgcolor='#161b22',
            yaxis_title="Total Profit / Loss ($)",
            xaxis_title="Date / Execution Time",
            height=420,
            margin=dict(l=20, r=20, t=30, b=20)
        )
        st.plotly_chart(fig, use_container_width=True)

# ================= TAB 2: STRATEGY & SIGNAL ENGINE =================
with tab_engine:
    st.subheader("5-Layer Live Operational Pipeline")
    st.markdown("""
    ```
    [Market Data Feed] ──► [Strategy 50% State Machine] ──► [Risk & Trailing Stop Engine] ──► [Broker API Router] ──► [Trade Logger]
    ```
    """)
    
    strat_status = st.session_state.strategy.get_status()
    risk_state = st.session_state.risk
    
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown("#### 1. Signal State Machine")
        st.write(f"**Dominant Bias:** `{strat_status['active_bias']}`")
        st.write(f"**Bullish State:** {strat_status['bull_state']}")
        st.write(f"**Bull Anchor:** {strat_status['bull_anchor']}")
        st.write(f"**Bull Peak:** {strat_status['bull_peak']}")
    with col_b:
        st.markdown("#### 2. Risk Engine & Position")
        st.write(f"**In Active Trade:** `{'YES' if risk_state.in_trade else 'NO (FLAT)'}`")
        if risk_state.in_trade:
            st.write(f"**Side:** `{risk_state.side}` @ `{risk_state.entry_price:.2f}`")
            st.write(f"**Stop Loss:** `{risk_state.sl_price:.2f}`")
            st.write(f"**Take Profit:** `{risk_state.tp_price:.2f}`")
            st.write(f"**Trailing SL Moved:** `{'YES' if risk_state.sl_moved else 'NO'}`")
        else:
            st.write("Ready for 50% Equilibrium touch.")
    with col_c:
        st.markdown("#### 3. Execution Router")
        st.write(f"**Connected Target:** `{st.session_state.strategy.asset}`")
        st.write(f"**Active Accounts:** `{active_count}`")
        st.write(f"**Slippage Model:** `2 Ticks Market Order`")
        st.write(f"**EOD Flatten Status:** `Arming for 15:59 EST`")

    st.markdown("---")
    st.subheader("Interactive Pipeline Simulation")
    st.write("Click below to simulate real-time 1-minute bars entering the pipeline and watch the signal generation, trade dispatch, and risk engine execute live:")
    
    sim_col1, sim_col2, sim_col3 = st.columns(3)
    
    if sim_col1.button("🚀 Simulate 09:30 AM RTH Open"):
        # Reset at open
        st.session_state.strategy.reset_at_open(18520.0, 18500.0)
        st.success("Slate wiped 100% clean at 09:30 AM EST! Anchor set to 18500.0, Peak set to 18520.0.")
        
    if sim_col2.button("📈 Simulate Bullish Impulse & 50% Touch"):
        # Simulate price expansion to 18540, then pull back to 50% (18520)
        st.session_state.strategy.day_low = 18500.0
        st.session_state.strategy.bull_anchor = 18500.0
        st.session_state.strategy.bull_extreme = 18540.0
        st.session_state.strategy.bull_state = 3
        st.session_state.strategy.active_bias = "BULL"
        
        # Bar touches 50% (18520.0)
        sig = st.session_state.strategy.process_bar(18530.0, 18519.0, 18525.0, is_entry_allowed=True)
        if sig:
            st.session_state.risk.open_position(sig)
            st.session_state.router.dispatch_entry(sig)
            st.success(f"SIGNAL FIRED & DISPATCHED! Long entered at 50% ({sig['entry_price']:.2f}) across all active accounts.")
            
    if sim_col3.button("🎯 Simulate Target Take Profit Hit"):
        if st.session_state.risk.in_trade:
            tp_price = st.session_state.risk.tp_price
            exit_event = st.session_state.risk.evaluate_bar(tp_price + 2.0, tp_price - 5.0, tp_price)
            if exit_event:
                st.session_state.router.dispatch_exit(
                    exit_event, st.session_state.risk.side, st.session_state.risk.entry_price
                )
                st.success(f"TAKE PROFIT HIT! Logged +{exit_event['pnl_points']:.2f} points to database. Check Tab 1!")
        else:
            st.warning("No active trade open. Click button 2 first to enter a trade!")

# ================= TAB 3: MULTI-ACCOUNT MANAGER =================
with tab_accounts:
    st.subheader("Prop Firm & Broker API Connections")
    st.markdown("Connect and manage multiple Topstep, Apex, Tradovate, or NinjaTrader accounts. The engine copies all orders concurrently.")
    
    # Display Current Accounts
    accs = get_accounts()
    if not accs.empty:
        st.dataframe(accs[['id', 'account_name', 'broker', 'contracts', 'is_active', 'created_at']], use_container_width=True)
        
        # Account Actions
        del_col1, del_col2 = st.columns(2)
        target_id = del_col1.number_input("Account ID to Toggle / Delete", min_value=1, step=1)
        if del_col2.button("Toggle Active / Inactive"):
            current_st = accs[accs['id'] == target_id]['is_active'].values
            if len(current_st) > 0:
                new_st = 0 if current_st[0] == 1 else 1
                toggle_account_status(target_id, new_st)
                st.success(f"Updated Account #{target_id} status to {'ACTIVE' if new_st == 1 else 'INACTIVE'}")
                st.rerun()
    else:
        st.info("No accounts configured yet. Add your first account below.")
        
    st.markdown("---")
    st.markdown("### Add New API Account")
    with st.form("add_account_form"):
        f_name = st.text_input("Account Name / Identifier (e.g., Topstep_100k_1)")
        f_broker = st.selectbox("Broker / Prop Firm Platform", ["Topstep (Tradovate)", "Apex Trader Funding", "Tradovate Live", "NinjaTrader API", "Interactive Brokers"])
        f_key = st.text_input("API Key / Username", type="password")
        f_secret = st.text_input("API Secret / Password", type="password")
        f_contracts = st.number_input("Contracts to Trade", min_value=1, max_value=50, value=3)
        
        submitted = st.form_submit_button("💾 Save Account to Platform")
        if submitted:
            if f_name and f_key:
                add_account(f_name, f_broker, f_key, f_secret, f_contracts)
                st.success(f"Account '{f_name}' connected successfully!")
                st.rerun()
            else:
                st.error("Please fill in Account Name and API Key.")

# ================= TAB 4: TRADE HISTORY & AUDIT =================
with tab_history:
    st.subheader("Complete Execution & Audit History")
    
    raw_trades = get_trades_df()
    if not raw_trades.empty:
        # Download Button
        csv_data = raw_trades.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Export Audit History to CSV",
            data=csv_data,
            file_name=f"quant_trade_history_{datetime.date.today()}.csv",
            mime="text/csv"
        )
        st.dataframe(raw_trades, use_container_width=True)
    else:
        st.info("Zero trades recorded. Trades will populate here in real-time as the engine executes.")
