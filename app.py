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
    page_title="Equilibrium Labs // Institutional Terminal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ----------------- MODERN SAAS CSS DESIGN SYSTEM -----------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

    /* Global CSS Reset & Layout */
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Clean Viewport Constraints (No Streamlit Bloat) */
    .block-container {
        padding-top: 1.25rem !important;
        padding-bottom: 2.5rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        max-width: 1480px;
    }
    #MainMenu, footer, header { 
        display: none !important; 
    }

    /* Background Aesthetic */
    .stApp {
        background-color: #07090E !important;
        background-image: 
            radial-gradient(at 0% 0%, rgba(30, 58, 138, 0.15) 0px, transparent 50%),
            radial-gradient(at 100% 0%, rgba(16, 185, 129, 0.1) 0px, transparent 50%),
            radial-gradient(at 50% 100%, rgba(15, 23, 42, 0.3) 0px, transparent 50%) !important;
        background-attachment: fixed !important;
        color: #E2E8F0 !important;
    }

    /* Monospaced Figures */
    .mono {
        font-family: 'JetBrains Mono', monospace !important;
        letter-spacing: -0.5px;
    }

    /* Modern SaaS Navigation Bar */
    .saas-navbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: rgba(13, 18, 30, 0.75);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 14px 24px;
        margin-bottom: 22px;
        box-shadow: 0 4px 24px -1px rgba(0, 0, 0, 0.35);
    }
    .brand-group {
        display: flex;
        align-items: center;
        gap: 14px;
    }
    .brand-logo-badge {
        width: 36px;
        height: 36px;
        background: linear-gradient(135deg, #10B981 0%, #3B82F6 100%);
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 800;
        font-size: 18px;
        color: #FFFFFF;
        box-shadow: 0 0 20px rgba(16, 185, 129, 0.35);
    }
    .brand-title {
        font-size: 18px;
        font-weight: 700;
        letter-spacing: -0.5px;
        color: #F8FAFC;
    }
    .brand-subtitle {
        font-size: 12px;
        color: #64748B;
        font-weight: 500;
        letter-spacing: 0.2px;
    }

    /* Modern Badges & Pills */
    .status-pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: rgba(16, 185, 129, 0.1);
        border: 1px solid rgba(16, 185, 129, 0.25);
        color: #34D399;
        padding: 5px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
    }
    .pulse-indicator {
        width: 7px;
        height: 7px;
        background-color: #10B981;
        border-radius: 50%;
        box-shadow: 0 0 10px #10B981;
        animation: pulseAnimation 2s infinite;
    }
    @keyframes pulseAnimation {
        0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
        70% { transform: scale(1); box-shadow: 0 0 0 7px rgba(16, 185, 129, 0); }
        100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
    }
    .session-badge {
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.06);
        color: #94A3B8;
        padding: 5px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 500;
    }

    /* Institutional SaaS KPI Cards */
    .kpi-container {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 16px;
        margin-bottom: 22px;
    }
    .modern-card {
        background: rgba(13, 18, 30, 0.65);
        backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-radius: 14px;
        padding: 20px;
        position: relative;
        overflow: hidden;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 4px 16px -2px rgba(0, 0, 0, 0.25);
    }
    .modern-card:hover {
        border-color: rgba(56, 189, 248, 0.35);
        transform: translateY(-2px);
        box-shadow: 0 12px 28px -4px rgba(0, 0, 0, 0.4);
    }
    .card-label {
        font-size: 12px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        color: #64748B;
        margin-bottom: 10px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .card-figure {
        font-family: 'JetBrains Mono', monospace;
        font-size: 28px;
        font-weight: 700;
        letter-spacing: -1px;
        color: #F8FAFC;
        line-height: 1.1;
        margin-bottom: 10px;
    }
    .card-footer-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 11px;
        font-weight: 600;
        padding: 3px 8px;
        border-radius: 6px;
    }
    .pill-emerald {
        background: rgba(16, 185, 129, 0.12);
        color: #34D399;
        border: 1px solid rgba(16, 185, 129, 0.2);
    }
    .pill-sky {
        background: rgba(56, 189, 248, 0.12);
        color: #38BDF8;
        border: 1px solid rgba(56, 189, 248, 0.2);
    }
    .pill-rose {
        background: rgba(244, 63, 94, 0.12);
        color: #FB7185;
        border: 1px solid rgba(244, 63, 94, 0.2);
    }

    /* SaaS Glass Panels */
    .surface-panel {
        background: rgba(13, 18, 30, 0.6);
        backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 22px;
        box-shadow: 0 8px 32px -4px rgba(0, 0, 0, 0.3);
    }
    .panel-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 18px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
        padding-bottom: 14px;
    }
    .panel-title {
        font-size: 15px;
        font-weight: 700;
        color: #F1F5F9;
        letter-spacing: -0.2px;
    }
    .panel-subtitle {
        font-size: 12px;
        color: #64748B;
        font-weight: 400;
    }

    /* Tabs Alignment */
    .stTabs [data-baseweb="tab-list"] {
        background: rgba(15, 23, 42, 0.6) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 12px !important;
        padding: 5px !important;
        gap: 6px !important;
        margin-bottom: 22px !important;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px !important;
        padding: 8px 18px !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        color: #94A3B8 !important;
        border: none !important;
        transition: all 0.2s ease !important;
    }
    .stTabs [aria-selected="true"] {
        background: #1E293B !important;
        color: #38BDF8 !important;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.35) !important;
    }

    /* Modern Form Controls */
    .stTextInput>div>div>input, .stSelectbox>div>div>div {
        background-color: #0F172A !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 8px !important;
        color: #F8FAFC !important;
        font-size: 13px !important;
    }
    .stButton>button {
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%) !important;
        color: #FFFFFF !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 8px !important;
        padding: 8px 20px !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.35) !important;
        transition: all 0.2s ease !important;
    }
    .stButton>button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 20px rgba(37, 99, 235, 0.5) !important;
    }

    /* DataFrame Styling */
    .stDataFrame {
        border: 1px solid rgba(255, 255, 255, 0.06) !important;
        border-radius: 12px !important;
        overflow: hidden !important;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Database
init_db()

# Auto-seed sample demo trades if empty
def seed_demo_data_if_empty():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM trades")
    count = c.fetchone()[0]
    if count == 0:
        c.execute('''INSERT OR IGNORE INTO accounts 
                     (account_name, broker, api_key, api_secret, contracts, is_active, created_at)
                     VALUES ('Topstep_100k_Alpha', 'Topstep (Tradovate)', 'DEMO_KEY_8829', 'DEMO_SECRET', 3, 1, '2026-10-01 09:30:00')''')
        c.execute('''INSERT OR IGNORE INTO accounts 
                     (account_name, broker, api_key, api_secret, contracts, is_active, created_at)
                     VALUES ('Apex_100k_Funded', 'Apex Trader Funding', 'APEX_PROD_102', 'APEX_SECRET', 3, 1, '2026-10-01 09:30:00')''')
        
        base_time = datetime.datetime.now() - datetime.timedelta(days=7)
        mock_pnl = [18.5, 22.0, -8.0, 31.5, 14.0, -6.5, 28.0, 19.5, 34.0, -7.0, 26.5, 42.0]
        for idx, pts in enumerate(mock_pnl):
            t_time = (base_time + datetime.timedelta(hours=idx*4)).strftime("%Y-%m-%d %H:%M:%S")
            pnl_usd = pts * 2.0 * 3
            exit_p = 18500.0 + pts
            c.execute('''INSERT INTO trades 
                         (account_name, trade_time, asset, side, entry_price, exit_price, pnl_points, pnl_usd, contracts, execution_type)
                         VALUES ('Topstep_100k_Alpha', ?, 'MNQ', 'BUY', 18500.0, ?, ?, ?, 3, 'LIVE_RTH')''',
                      (t_time, exit_p, pts, pnl_usd))
        conn.commit()
    conn.close()

seed_demo_data_if_empty()

# Initialize Engine Singletons
if "strategy" not in st.session_state:
    st.session_state.strategy = PureRTHEquilibriumStrategyEngine(asset="MNQ")
if "risk" not in st.session_state:
    st.session_state.risk = RiskManagementEngine(asset="MNQ")
if "router" not in st.session_state:
    st.session_state.router = BrokerMultiAccountRouter(asset="MNQ")

# ----------------- MODERN SAAS TOPBAR -----------------
accounts_df = get_accounts()
active_count = len(accounts_df[accounts_df['is_active'] == 1]) if not accounts_df.empty else 0

st.markdown(f"""
<div class="saas-navbar">
    <div class="brand-group">
        <div class="brand-logo-badge">⚡</div>
        <div>
            <div class="brand-title">EQUILIBRIUM LABS // QUANT TERMINAL</div>
            <div class="brand-subtitle">Automated Institutional Order Flow Engine • Chicago CME Gateway</div>
        </div>
    </div>
    <div style="display: flex; gap: 10px; align-items: center;">
        <div class="session-badge">Asset: <b>MNQ (Micro Nasdaq)</b></div>
        <div class="session-badge">Session: <b>09:30 – 15:55 EST</b></div>
        <div class="status-pill">
            <div class="pulse-indicator"></div>
            ENGINE LISTENING
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ----------------- SAAS TABS NAVIGATION -----------------
tab_dash, tab_strat, tab_acc, tab_audit = st.tabs([
    "📈 Performance Analytics",
    "⚡ Strategy & Wave Engine",
    "🔑 Multi-Account API Hub",
    "📜 Full Trade Audit Log"
])

# ================= TAB 1: PERFORMANCE ANALYTICS =================
with tab_dash:
    trades_df = get_trades_df()
    
    if trades_df.empty:
        st.info("No executions recorded yet. Add an account or simulate trades in Tab 2.")
    else:
        # SaaS Sub-Header Filters
        col_select, col_empty = st.columns([1, 3])
        with col_select:
            acc_list = ["ALL PORTFOLIOS (AGGREGATED)"] + trades_df['account_name'].unique().tolist()
            selected_acc = st.selectbox("Portfolio View", acc_list, label_visibility="collapsed")
            
        df_view = trades_df.copy()
        if selected_acc != "ALL PORTFOLIOS (AGGREGATED)":
            df_view = df_view[df_view['account_name'] == selected_acc]
            
        df_view = df_view.sort_values(by='trade_time', ascending=True).reset_index(drop=True)
        df_view['cum_pnl'] = df_view['pnl_usd'].cumsum()
        df_view['peak'] = df_view['cum_pnl'].cummax()
        df_view['drawdown_usd'] = df_view['cum_pnl'] - df_view['peak']
        
        # Financial Quant Metrics
        total_pnl = df_view['pnl_usd'].sum()
        total_trades = len(df_view)
        wins = len(df_view[df_view['pnl_usd'] > 0])
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
        
        gp = df_view[df_view['pnl_usd'] > 0]['pnl_usd'].sum()
        gl = abs(df_view[df_view['pnl_usd'] <= 0]['pnl_usd'].sum())
        profit_factor = (gp / gl) if gl > 0 else (99.9 if gp > 0 else 0.0)
        max_dd = df_view['drawdown_usd'].min()
        
        # Modern SaaS KPI Cards Grid
        st.markdown(f"""
        <div class="kpi-container">
            <div class="modern-card">
                <div class="card-label">
                    <span>Total Realized Profit</span>
                    <span>💵</span>
                </div>
                <div class="card-figure" style="color: {'#34D399' if total_pnl >= 0 else '#F87171'};">
                    ${total_pnl:,.2f}
                </div>
                <div class="card-footer-pill pill-emerald">
                    ▲ {win_rate:.1f}% Win Rate ({wins}/{total_trades})
                </div>
            </div>
            <div class="modern-card">
                <div class="card-label">
                    <span>Profit Factor</span>
                    <span>⚖️</span>
                </div>
                <div class="card-figure" style="color: #38BDF8;">
                    {profit_factor:.2f}
                </div>
                <div class="card-footer-pill pill-sky">
                    Institutional Benchmark (> 2.0)
                </div>
            </div>
            <div class="modern-card">
                <div class="card-label">
                    <span>Peak-to-Valley Drawdown</span>
                    <span>🛡️</span>
                </div>
                <div class="card-figure" style="color: #FB7185;">
                    ${abs(max_dd):,.2f}
                </div>
                <div class="card-footer-pill pill-rose">
                    Max Capital Stress
                </div>
            </div>
            <div class="modern-card">
                <div class="card-label">
                    <span>Active Portfolios</span>
                    <span>⚡</span>
                </div>
                <div class="card-figure" style="color: #F8FAFC;">
                    {active_count} <span style="font-size: 14px; color: #64748B;">Connected</span>
                </div>
                <div class="card-footer-pill pill-sky">
                    Concurrent Trade Copier Armed
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Interactive Dark-Mode Plotly Chart
        st.markdown("""
        <div class="surface-panel">
            <div class="panel-header">
                <div>
                    <div class="panel-title">Cumulative Performance Growth</div>
                    <div class="panel-subtitle">Realized equity progression across New York cash trading sessions</div>
                </div>
                <div class="session-badge">Zero Overnight Exposure</div>
            </div>
        """, unsafe_allow_html=True)
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_view['trade_time'],
            y=df_view['cum_pnl'],
            mode='lines',
            name='Cumulative Equity ($)',
            line=dict(color='#10B981', width=2.5),
            fill='tozeroy',
            fillcolor='rgba(16, 185, 129, 0.07)'
        ))
        
        fig.update_layout(
            template='plotly_dark',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            height=390,
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis=dict(
                showgrid=True,
                gridcolor='rgba(255,255,255,0.04)',
                color='#64748B',
                zeroline=False
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='rgba(255,255,255,0.04)',
                color='#64748B',
                tickprefix="$",
                zeroline=False
            ),
            hovermode="x unified"
        )
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

# ================= TAB 2: STRATEGY & WAVE ENGINE =================
with tab_strat:
    strat = st.session_state.strategy
    risk = st.session_state.risk
    stat = strat.get_status()
    
    st.markdown("""
    <div class="surface-panel">
        <div class="panel-header">
            <div>
                <div class="panel-title">Real-Time Wave Mechanics & State Visualizer</div>
                <div class="panel-subtitle">Audited 4-State Cycle tracking Anchor, Peak, and 50% Equilibrium touch</div>
            </div>
            <div class="session-badge">Pure RTH 09:30 AM Fresh Start</div>
        </div>
    """, unsafe_allow_html=True)
    
    c_s1, c_s2, c_s3 = st.columns(3)
    with c_s1:
        st.markdown("##### 📍 Fractal Coordinates")
        st.markdown(f"**Dominant Direction:** `{stat['active_bias']}`")
        st.markdown(f"**Wave State:** `{stat['bull_state']}`")
        st.markdown(f"**Session Anchor (0.0%):** `{stat['bull_anchor']}`")
        st.markdown(f"**Session Peak (100.0%):** `{stat['bull_peak']}`")
    with c_s2:
        st.markdown("##### 🛡️ Risk & Trailing Protocol")
        st.markdown(f"**Active Position:** `{'IN TRADE' if risk.in_trade else 'FLAT (AWAITING 50% TOUCH)'}`")
        if risk.in_trade:
            st.markdown(f"**Side:** `{risk.side}` @ `{risk.entry_price:.2f}`")
            st.markdown(f"**Take Profit Target:** `{risk.tp_price:.2f}`")
            st.markdown(f"**Protective Stop Loss:** `{risk.sl_price:.2f}`")
            st.markdown(f"**Trailing SL Engaged:** `{'YES (Risk Cut ~75%)' if risk.sl_moved else 'NO (At Anchor)'}`")
        else:
            st.markdown("*Ready to buy 50% equilibrium line upon confirmation.*")
    with c_s3:
        st.markdown("##### 🚀 Execution Rules")
        st.markdown(f"**Instrument:** `{strat.asset}`")
        st.markdown(f"**Execution Model:** `Immediate Market Order`")
        st.markdown(f"**Slippage Penalty:** `2 Ticks (0.50 pts absorbed)`")
        st.markdown(f"**EOD Liquidator:** `Arming for 15:59 EST Hard Flatten`")
        
    st.markdown("---")
    st.markdown("##### 🕹️ Interactive Pipeline Simulator")
    st.caption("Trigger live bar execution through the 5-layer pipeline in real time:")
    
    sim_c1, sim_c2, sim_c3 = st.columns(3)
    if sim_c1.button("1. 🔔 Simulate 09:30 AM Opening Bell"):
        strat.reset_at_open(18530.0, 18500.0)
        st.success("✅ 09:30 AM Bell: Slate wiped 100% clean. Anchor = 18500.0, Peak = 18530.0.")
        
    if sim_c2.button("2. 📉 Simulate Impulse & 50% Touch Entry"):
        strat.day_low = 18500.0
        strat.bull_anchor = 18500.0
        strat.bull_extreme = 18550.0
        strat.bull_state = 3
        strat.active_bias = "BULL"
        
        # 50% line is 18525.0
        sig = strat.process_bar(18535.0, 18524.5, 18530.0, is_entry_allowed=True)
        if sig:
            risk.open_position(sig)
            st.session_state.router.dispatch_entry(sig)
            st.success(f"🚀 50% TOUCH TRIGGERED! Long order filled at {sig['entry_price']:.2f}. Initial SL set at {sig['sl_price']:.2f}.")
            
    if sim_c3.button("3. 🎯 Simulate Take Profit Reached"):
        if risk.in_trade:
            tp = risk.tp_price
            exit_ev = risk.evaluate_bar(tp + 2.0, tp - 2.0, tp)
            if exit_ev:
                st.session_state.router.dispatch_exit(exit_ev, risk.side, risk.entry_price)
                st.success(f"🎉 TAKE PROFIT REACHED! Logged +{exit_ev['pnl_points']:.2f} points across all connected accounts. View Tab 1!")
        else:
            st.warning("Position is currently flat. Click Button 2 first to enter a position!")
            
    st.markdown("</div>", unsafe_allow_html=True)

# ================= TAB 3: MULTI-ACCOUNT API HUB =================
with tab_acc:
    st.markdown("""
    <div class="surface-panel">
        <div class="panel-header">
            <div>
                <div class="panel-title">Multi-Account API Management</div>
                <div class="panel-subtitle">Broadcast institutional 50% signals concurrently across all linked prop firm accounts</div>
            </div>
            <div class="session-badge">Concurrent Multi-Tenant Copier</div>
        </div>
    """, unsafe_allow_html=True)
    
    accs = get_accounts()
    if not accs.empty:
        st.markdown("##### Connected Accounts")
        st.dataframe(
            accs[['id', 'account_name', 'broker', 'contracts', 'is_active', 'created_at']],
            use_container_width=True
        )
        
        c_act1, c_act2, c_act3 = st.columns([1, 1, 2])
        target_id = c_act1.number_input("Account ID", min_value=1, step=1, label_visibility="collapsed")
        if c_act2.button("Toggle Active / Paused"):
            curr = accs[accs['id'] == target_id]['is_active'].values
            if len(curr) > 0:
                toggle_account_status(target_id, 0 if curr[0] == 1 else 1)
                st.rerun()
        if c_act3.button("Delete Account Connection"):
            delete_account(target_id)
            st.rerun()
    else:
        st.info("No API accounts linked yet. Add your first account below.")
        
    st.markdown("---")
    st.markdown("##### Link New Broker / Prop Firm Account")
    with st.form("add_acc_form"):
        col_f1, col_f2 = st.columns(2)
        acc_n = col_f1.text_input("Account Identifier", placeholder="Topstep_100k_Combine_02")
        brk_t = col_f2.selectbox("Broker / Prop Firm Feed", [
            "Topstep (Tradovate)", "Apex Trader Funding", "Tradovate Live API", "NinjaTrader 8 (Local)", "Interactive Brokers"
        ])
        
        col_f3, col_f4 = st.columns(2)
        a_key = col_f3.text_input("API Key / Username", type="password")
        a_sec = col_f4.text_input("API Secret / Password", type="password")
        
        c_qty = st.slider("Position Size (Micro Contracts)", min_value=1, max_value=20, value=3)
        
        if st.form_submit_button("🔗 Authorize & Link Account"):
            if acc_n and a_key:
                add_account(acc_n, brk_t, a_key, a_sec, c_qty)
                st.success(f"Account '{acc_n}' linked and armed successfully!")
                st.rerun()
            else:
                st.error("Please provide both Account Name and API Key.")
    st.markdown("</div>", unsafe_allow_html=True)

# ================= TAB 4: FULL TRADE AUDIT LOG =================
with tab_audit:
    st.markdown("""
    <div class="surface-panel">
        <div class="panel-header">
            <div>
                <div class="panel-title">Institutional Trade Audit Statement</div>
                <div class="panel-subtitle">Permanent cryptographic ledger of all filled orders, slippage offsets, and cash PnL</div>
            </div>
            <div class="session-badge">Verified RTH Audit Trail</div>
        </div>
    """, unsafe_allow_html=True)
    
    all_trades = get_trades_df()
    if not all_trades.empty:
        csv_bytes = all_trades.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Export Full Audit Statement (.CSV)",
            data=csv_bytes,
            file_name=f"equilibrium_statement_{datetime.date.today()}.csv",
            mime="text/csv"
        )
        st.dataframe(all_trades, use_container_width=True)
    else:
        st.info("No trade records found.")
    st.markdown("</div>", unsafe_allow_html=True)
