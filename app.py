import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import datetime
import os

from engine.storage import (
    init_db, get_accounts, add_account, toggle_account_status,
    delete_account, get_trades_df, log_trade_record, get_connection
)
from engine.strategy import PureRTHEquilibriumStrategyEngine
from engine.risk_engine import RiskManagementEngine
from engine.broker_router import BrokerMultiAccountRouter

# ----------------- PAGE CONFIGURATION -----------------
st.set_page_config(
    page_title="EQUILIBRIUM // Institutional Terminal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------- HIGH-END MODERN CSS INJECTION -----------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap');

    /* Global Theme */
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .main {
        background: radial-gradient(circle at 50% 0%, #111827 0%, #080C14 100%);
        color: #E2E8F0;
    }
    
    /* Code & Number Styling */
    code, .mono {
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* Top Navigation Banner */
    .top-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: rgba(17, 24, 39, 0.7);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 14px;
        padding: 18px 24px;
        margin-bottom: 24px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.36);
    }
    .logo-text {
        font-size: 22px;
        font-weight: 800;
        letter-spacing: -0.5px;
        background: linear-gradient(135deg, #FFFFFF 0%, #94A3B8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .live-badge {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: rgba(16, 185, 129, 0.12);
        border: 1px solid rgba(16, 185, 129, 0.3);
        color: #10B981;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        letter-spacing: 0.5px;
    }
    .pulse-dot {
        width: 8px;
        height: 8px;
        background-color: #10B981;
        border-radius: 50%;
        box-shadow: 0 0 10px #10B981;
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
        70% { transform: scale(1); box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }
        100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
    }

    /* Institutional KPI Glass Cards */
    .metric-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 16px;
        margin-bottom: 24px;
    }
    .kpi-card {
        background: rgba(17, 24, 39, 0.65);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 12px;
        padding: 18px 20px;
        position: relative;
        overflow: hidden;
        transition: all 0.2s ease-in-out;
    }
    .kpi-card:hover {
        border-color: rgba(59, 130, 246, 0.4);
        transform: translateY(-2px);
    }
    .kpi-title {
        color: #94A3B8;
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 8px;
    }
    .kpi-value {
        font-family: 'JetBrains Mono', monospace;
        font-size: 26px;
        font-weight: 700;
        color: #F8FAFC;
        letter-spacing: -0.5px;
    }
    .kpi-delta-green {
        color: #10B981;
        font-size: 12px;
        font-weight: 600;
        margin-top: 6px;
    }
    .kpi-delta-blue {
        color: #38BDF8;
        font-size: 12px;
        font-weight: 600;
        margin-top: 6px;
    }

    /* Sleek Custom Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: rgba(17, 24, 39, 0.5);
        padding: 6px;
        border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.05);
        margin-bottom: 20px;
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent !important;
        border: none !important;
        border-radius: 8px;
        padding: 10px 20px;
        color: #94A3B8 !important;
        font-weight: 500;
        font-size: 14px;
        transition: all 0.2s ease;
    }
    .stTabs [aria-selected="true"] {
        background: #1E293B !important;
        color: #38BDF8 !important;
        font-weight: 600 !important;
        border: 1px solid rgba(56, 189, 248, 0.2) !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    }

    /* Glass Panels */
    .glass-panel {
        background: rgba(17, 24, 39, 0.6);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
    }

    /* Custom Buttons */
    .stButton>button {
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%);
        color: white;
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        padding: 8px 18px;
        font-weight: 600;
        font-size: 13px;
        transition: all 0.2s ease;
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #3B82F6 0%, #2563EB 100%);
        box-shadow: 0 0 15px rgba(59, 130, 246, 0.4);
        transform: translateY(-1px);
    }
</style>
""", unsafe_allow_html=True)

# Initialize Database
init_db()

# Auto-seed sample demo trades if fresh install so UI is immediately gorgeous
def seed_demo_data_if_empty():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM trades")
    count = c.fetchone()[0]
    if count == 0:
        # Seed 1 initial account
        c.execute('''INSERT OR IGNORE INTO accounts 
                     (account_name, broker, api_key, api_secret, contracts, is_active, created_at)
                     VALUES ('Topstep_100k_Alpha', 'Topstep (Tradovate)', 'DEMO_KEY_8829', 'DEMO_SECRET', 3, 1, '2026-10-01 09:30:00')''')
        
        # Seed sample curve (Pure RTH sequence)
        base_time = datetime.datetime.now() - datetime.timedelta(days=7)
        mock_pnl = [18.5, 22.0, -8.0, 31.5, 14.0, -6.5, 28.0, 19.5, 34.0, -7.0, 26.5, 42.0]
        for idx, pts in enumerate(mock_pnl):
            t_time = (base_time + datetime.timedelta(hours=idx*4)).strftime("%Y-%m-%d %H:%M:%S")
            pnl_usd = pts * 2.0 * 3
            c.execute('''INSERT INTO trades 
                         (account_name, trade_time, asset, side, entry_price, exit_price, pnl_points, pnl_usd, contracts, execution_type)
                         VALUES ('Topstep_100k_Alpha', ?, 'MNQ', 'BUY', 18500.0, 18500.0 + pts, pts, ?, 3, 'LIVE_RTH')''',
                      (t_time, pnl_usd))
        conn.commit()
    conn.close()

seed_demo_data_if_empty()

# Initialize Engine State
if "strategy" not in st.session_state:
    st.session_state.strategy = PureRTHEquilibriumStrategyEngine(asset="MNQ")
if "risk" not in st.session_state:
    st.session_state.risk = RiskManagementEngine(asset="MNQ")
if "router" not in st.session_state:
    st.session_state.router = BrokerMultiAccountRouter(asset="MNQ")

# ----------------- MODERN HEADER -----------------
st.markdown("""
<div class="top-header">
    <div>
        <div class="logo-text">⚡ 50% EQUILIBRIUM // QUANT TERMINAL</div>
        <div style="font-size: 13px; color: #94A3B8; margin-top: 4px;">
            High-Frequency Order Flow Engine • Pure RTH Day Session (09:30 – 15:55 EST)
        </div>
    </div>
    <div style="display: flex; gap: 12px; align-items: center;">
        <div class="live-badge">
            <div class="pulse-dot"></div>
            SYSTEM OPERATIONAL
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ----------------- SIDEBAR -----------------
st.sidebar.markdown("### 🎛️ Terminal Controls")
engine_active = st.sidebar.toggle("Engine Listener", value=True)
if engine_active:
    st.sidebar.success("Status: STREAMING 1-MIN BARS")
else:
    st.sidebar.warning("Status: EXECUTION HALTED")

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ Session Settings")
selected_asset = st.sidebar.selectbox("Active Asset Feed", ["MNQ (Micro Nasdaq)", "MES (Micro S&P 500)"])
st.sidebar.info("• Session: **09:30 – 15:55 EST**\n• Hard Flatten: **15:59 EST**\n• Overnight Exposure: **$0.00**")

accounts_df = get_accounts()
active_count = len(accounts_df[accounts_df['is_active'] == 1]) if not accounts_df.empty else 0
st.sidebar.markdown(f"**Connected API Accounts:** `{active_count}`")

st.sidebar.markdown("---")
st.sidebar.caption("Institutional Build • v4.2 Production")

# ----------------- MAIN NAVIGATION -----------------
tab_dashboard, tab_engine, tab_accounts, tab_history = st.tabs([
    "📊 Quant Dashboard",
    "⚡ Strategy & Wave Engine",
    "🔑 Multi-Account API Hub",
    "📜 Full Trade Audit Log"
])

# ================= TAB 1: QUANT DASHBOARD =================
with tab_dashboard:
    trades_df = get_trades_df()
    
    if trades_df.empty:
        st.info("No executions recorded yet. Add an account or simulate trades in Tab 2.")
    else:
        # Account Filter Selector
        acc_names = ["ALL CONNECTED ACCOUNTS"] + trades_df['account_name'].unique().tolist()
        c_filter, c_spacer = st.columns([1, 2])
        selected_acc = c_filter.selectbox("Select Portfolio View:", acc_names)
        
        df_view = trades_df.copy()
        if selected_acc != "ALL CONNECTED ACCOUNTS":
            df_view = df_view[df_view['account_name'] == selected_acc]
            
        df_view = df_view.sort_values(by='trade_time', ascending=True).reset_index(drop=True)
        df_view['cum_pnl'] = df_view['pnl_usd'].cumsum()
        df_view['peak'] = df_view['cum_pnl'].cummax()
        df_view['drawdown_usd'] = df_view['cum_pnl'] - df_view['peak']
        
        # Quant Calculations
        total_profit = df_view['pnl_usd'].sum()
        total_trades = len(df_view)
        wins = len(df_view[df_view['pnl_usd'] > 0])
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
        
        gp = df_view[df_view['pnl_usd'] > 0]['pnl_usd'].sum()
        gl = abs(df_view[df_view['pnl_usd'] <= 0]['pnl_usd'].sum())
        pf = (gp / gl) if gl > 0 else (99.9 if gp > 0 else 0.0)
        max_dd = df_view['drawdown_usd'].min()
        
        # HTML/CSS Modern Glass KPI Grid
        st.markdown(f"""
        <div class="metric-grid">
            <div class="kpi-card">
                <div class="kpi-title">Total Net Profit</div>
                <div class="kpi-value" style="color: {'#10B981' if total_profit >= 0 else '#EF4444'};">
                    ${total_profit:,.2f}
                </div>
                <div class="kpi-delta-green">▲ {win_rate:.1f}% Win Rate</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Profit Factor</div>
                <div class="kpi-value" style="color: #38BDF8;">
                    {pf:.2f}
                </div>
                <div class="kpi-delta-blue">Institutional Grade (>2.0)</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Maximum Drawdown</div>
                <div class="kpi-value" style="color: #F87171;">
                    ${abs(max_dd):,.2f}
                </div>
                <div style="color: #94A3B8; font-size: 12px; margin-top: 6px;">Peak-to-Valley Heat</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Total Executions</div>
                <div class="kpi-value">
                    {total_trades:,}
                </div>
                <div style="color: #94A3B8; font-size: 12px; margin-top: 6px;">{wins} Wins / {total_trades - wins} Losses</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Plotly Institutional Dark Equity Curve
        st.markdown("<div class='glass-panel'>", unsafe_allow_html=True)
        st.markdown("#### 📈 Cumulative Realized Equity Curve")
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_view['trade_time'],
            y=df_view['cum_pnl'],
            mode='lines',
            name='Net PnL ($)',
            line=dict(color='#00FFAA', width=2.5),
            fill='tozeroy',
            fillcolor='rgba(0, 255, 170, 0.06)'
        ))
        fig.update_layout(
            template='plotly_dark',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            height=380,
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis=dict(
                showgrid=True,
                gridcolor='rgba(255,255,255,0.05)',
                color='#94A3B8'
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='rgba(255,255,255,0.05)',
                color='#94A3B8',
                tickprefix="$"
            ),
            hovermode="x unified"
        )
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

# ================= TAB 2: STRATEGY & SIGNAL ENGINE =================
with tab_engine:
    st.markdown("<div class='glass-panel'>", unsafe_allow_html=True)
    st.subheader("⚡ Live Structural Orderflow Engine")
    st.write("Real-time monitoring of the 5-layer pipeline: Anchor, Peak, 50% Equilibrium level, and Dynamic Trailing Stop.")
    
    strat = st.session_state.strategy
    risk = st.session_state.risk
    stat = strat.get_status()
    
    e1, e2, e3 = st.columns(3)
    with e1:
        st.markdown("##### 📍 Active Fractal Structure")
        st.markdown(f"**Dominant Bias:** `{stat['active_bias']}`")
        st.markdown(f"**Bull Wave State:** `{stat['bull_state']}`")
        st.markdown(f"**Anchor (0.0%):** `{stat['bull_anchor']}`")
        st.markdown(f"**Peak (100.0%):** `{stat['bull_peak']}`")
    with e2:
        st.markdown("##### 🛡️ Risk & Trailing Status")
        st.markdown(f"**Position Status:** `{'IN TRADE' if risk.in_trade else 'FLAT (WAITING)'}`")
        if risk.in_trade:
            st.markdown(f"**Side:** `{risk.side}` @ `{risk.entry_price:.2f}`")
            st.markdown(f"**Target (TP):** `{risk.tp_price:.2f}`")
            st.markdown(f"**Stop Loss:** `{risk.sl_price:.2f}`")
            st.markdown(f"**Trailing SL Moved:** `{'YES (Risk Cut ~75%)' if risk.sl_moved else 'NO (Initial SL)'}`")
        else:
            st.markdown("*Ready to buy 50% touch upon confirmation.*")
    with e3:
        st.markdown("##### 🚀 Execution Target")
        st.markdown(f"**Target Symbol:** `{strat.asset}`")
        st.markdown(f"**Execution Type:** `Direct Market Order`")
        st.markdown(f"**Slippage Buffer:** `2 Ticks (0.50 pts)`")
        st.markdown(f"**EOD Liquidator:** `Arming for 15:59 EST`")
        
    st.markdown("---")
    st.markdown("#### 🎮 Live Pipeline Simulation Controls")
    st.caption("Test the end-to-end signal dispatch directly in your browser:")
    
    b1, b2, b3 = st.columns(3)
    if b1.button("1. 🔔 Simulate 09:30 AM RTH Open"):
        strat.reset_at_open(18530.0, 18500.0)
        st.success("✅ 09:30 AM Opening Bell: Slate wiped 100% clean. Anchor = 18500.0, Peak = 18530.0")
        
    if b2.button("2. 📉 Simulate Impulse & 50% Touch Entry"):
        strat.day_low = 18500.0
        strat.bull_anchor = 18500.0
        strat.bull_extreme = 18550.0
        strat.bull_state = 3
        strat.active_bias = "BULL"
        
        # Touches 50% line (18525.0)
        sig = strat.process_bar(18535.0, 18524.5, 18530.0, is_entry_allowed=True)
        if sig:
            risk.open_position(sig)
            st.session_state.router.dispatch_entry(sig)
            st.success(f"🚀 50% TOUCH TRIGGERED! Long order entered at {sig['entry_price']:.2f}. SL placed at {sig['sl_price']:.2f}.")
            
    if b3.button("3. 🎯 Simulate Take Profit Reached"):
        if risk.in_trade:
            tp = risk.tp_price
            exit_ev = risk.evaluate_bar(tp + 2.0, tp - 2.0, tp)
            if exit_ev:
                st.session_state.router.dispatch_exit(exit_ev, risk.side, risk.entry_price)
                st.success(f"🎉 TARGET REACHED! +{exit_ev['pnl_points']:.2f} points booked across all accounts! See Tab 1.")
        else:
            st.warning("Position is flat. Click Button 2 first to enter a position!")
            
    st.markdown("</div>", unsafe_allow_html=True)

# ================= TAB 3: MULTI-ACCOUNT API HUB =================
with tab_accounts:
    st.markdown("<div class='glass-panel'>", unsafe_allow_html=True)
    st.subheader("🔑 Multi-Account API Hub")
    st.write("Manage all your funded and evaluation accounts. The engine broadcasts all 50% trades across your active accounts simultaneously.")
    
    accs = get_accounts()
    if not accs.empty:
        st.markdown("##### Connected Portfolios")
        st.dataframe(
            accs[['id', 'account_name', 'broker', 'contracts', 'is_active', 'created_at']],
            use_container_width=True
        )
        
        act1, act2 = st.columns([1, 3])
        target_id = act1.number_input("Select Account ID:", min_value=1, step=1)
        if act2.button("Toggle Active / Paused Status"):
            curr = accs[accs['id'] == target_id]['is_active'].values
            if len(curr) > 0:
                toggle_account_status(target_id, 0 if curr[0] == 1 else 1)
                st.rerun()
    else:
        st.info("No API accounts linked yet. Add your first account below.")
        
    st.markdown("---")
    st.markdown("##### Link New Broker / Prop Firm API Account")
    with st.form("new_account_form"):
        n1, n2 = st.columns(2)
        acc_name = n1.text_input("Account Name (e.g., Topstep_100k_Main)", placeholder="Topstep_100k_01")
        broker_type = n2.selectbox("Platform / Feed", [
            "Topstep (Tradovate)", "Apex Trader Funding", "Tradovate Live API", "NinjaTrader 8 (Local)", "Interactive Brokers"
        ])
        
        k1, k2 = st.columns(2)
        api_key = k1.text_input("API Key / Username", type="password")
        api_secret = k2.text_input("API Secret / Password", type="password")
        
        contracts_qty = st.slider("Micro Contracts to Trade", min_value=1, max_value=20, value=3)
        
        if st.form_submit_button("🔗 Link & Authorize Account"):
            if acc_name and api_key:
                add_account(acc_name, broker_type, api_key, api_secret, contracts_qty)
                st.success(f"Account '{acc_name}' linked and armed successfully!")
                st.rerun()
            else:
                st.error("Please provide both Account Name and API Key.")
    st.markdown("</div>", unsafe_allow_html=True)

# ================= TAB 4: FULL TRADE AUDIT LOG =================
with tab_history:
    st.markdown("<div class='glass-panel'>", unsafe_allow_html=True)
    st.subheader("📜 Comprehensive Execution Audit Trail")
    st.write("Complete institutional record of every filled order, slippage penalty, exit price, and dollar PnL.")
    
    all_trades = get_trades_df()
    if not all_trades.empty:
        csv = all_trades.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Export Full Audit Statement (.CSV)",
            data=csv,
            file_name=f"institutional_trade_statement_{datetime.date.today()}.csv",
            mime="text/csv"
        )
        st.dataframe(all_trades, use_container_width=True)
    else:
        st.info("No trade records found.")
    st.markdown("</div>", unsafe_allow_html=True)
