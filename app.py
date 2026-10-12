import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import datetime
import calendar
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
    page_title="Equilibrium // Minimal Terminal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ----------------- MINIMALIST SAAS DESIGN SYSTEM -----------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

    /* Reset & Viewport Constraints */
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 2.5rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        max-width: 1440px;
    }
    #MainMenu, footer, header { display: none !important; }

    /* Minimalist Dark Canvas */
    .stApp {
        background-color: #090B0E !important;
        background-image: radial-gradient(at 50% 0%, rgba(30, 41, 59, 0.2) 0px, transparent 60%) !important;
        color: #E2E8F0 !important;
    }
    .mono { font-family: 'JetBrains Mono', monospace !important; }

    /* Minimal Top Navigation Bar */
    .nav-minimal {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: #0E1218;
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-radius: 12px;
        padding: 10px 18px;
        margin-bottom: 18px;
    }
    .nav-left {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .nav-brand {
        font-size: 15px;
        font-weight: 700;
        letter-spacing: -0.3px;
        color: #F8FAFC;
    }
    .nav-sub {
        font-size: 11px;
        color: #64748B;
        font-weight: 500;
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }
    .nav-right {
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .nav-tag {
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.06);
        color: #94A3B8;
        font-size: 11px;
        font-weight: 500;
        padding: 4px 10px;
        border-radius: 6px;
    }
    .nav-status {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(16, 185, 129, 0.08);
        border: 1px solid rgba(16, 185, 129, 0.2);
        color: #34D399;
        font-size: 11px;
        font-weight: 600;
        padding: 4px 10px;
        border-radius: 6px;
    }
    .dot-live {
        width: 6px;
        height: 6px;
        background-color: #10B981;
        border-radius: 50%;
        box-shadow: 0 0 8px #10B981;
    }

    /* Minimalist KPI Row (5-Cards Equal Grid) */
    .kpi-row {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 12px;
        margin-bottom: 18px;
    }
    .kpi-card {
        background: #0E1218;
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-radius: 12px;
        padding: 14px 16px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        min-height: 98px;
        transition: border-color 0.2s ease;
    }
    .kpi-card:hover {
        border-color: rgba(255, 255, 255, 0.15);
    }
    .kpi-header {
        font-size: 11px;
        font-weight: 600;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.6px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .kpi-value {
        font-family: 'JetBrains Mono', monospace;
        font-size: 20px;
        font-weight: 700;
        color: #F8FAFC;
        letter-spacing: -0.5px;
        margin: 4px 0;
    }
    .kpi-sub {
        font-size: 11px;
        font-weight: 500;
        color: #94A3B8;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .micro-progress {
        background: rgba(255, 255, 255, 0.06);
        border-radius: 999px;
        height: 3px;
        width: 100%;
        overflow: hidden;
        margin: 6px 0;
    }
    .micro-fill-emerald {
        height: 100%;
        background: #10B981;
        border-radius: 999px;
    }
    .micro-fill-sky {
        height: 100%;
        background: #38BDF8;
        border-radius: 999px;
    }
    .micro-fill-amber {
        height: 100%;
        background: #F59E0B;
        border-radius: 999px;
    }
    .micro-fill-rose {
        height: 100%;
        background: #F43F5E;
        border-radius: 999px;
    }

    /* Minimalist Content Panels */
    .panel-box {
        background: #0E1218;
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-radius: 12px;
        padding: 18px 20px;
        margin-bottom: 18px;
    }
    .panel-top {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 14px;
        padding-bottom: 10px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }
    .panel-heading {
        font-size: 13px;
        font-weight: 700;
        color: #F1F5F9;
        letter-spacing: -0.2px;
        text-transform: uppercase;
    }
    .panel-meta {
        font-size: 11px;
        color: #64748B;
        font-weight: 500;
    }

    /* Minimalist Calendar */
    .cal-header-bar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
        font-size: 12px;
    }
    .cal-stats-inline {
        display: flex;
        gap: 16px;
        font-size: 12px;
        color: #94A3B8;
    }
    .cal-weekdays {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 8px;
        margin-bottom: 6px;
    }
    .cal-weekday-th {
        text-align: center;
        font-size: 10px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        color: #475569;
        padding: 4px 0;
    }
    .cal-grid {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 8px;
    }
    .day-box {
        border-radius: 8px;
        padding: 8px 10px;
        min-height: 64px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        border: 1px solid rgba(255, 255, 255, 0.05);
        background: #0B0E13;
        transition: border-color 0.15s ease;
    }
    .day-box:hover {
        border-color: rgba(255, 255, 255, 0.18);
    }
    .day-green {
        background: rgba(16, 185, 129, 0.06);
        border: 1px solid rgba(16, 185, 129, 0.22);
    }
    .day-red {
        background: rgba(244, 63, 94, 0.06);
        border: 1px solid rgba(244, 63, 94, 0.22);
    }
    .day-num {
        font-size: 10px;
        font-weight: 600;
        color: #64748B;
        font-family: 'JetBrains Mono', monospace;
    }
    .day-pnl {
        font-family: 'JetBrains Mono', monospace;
        font-size: 13px;
        font-weight: 700;
        letter-spacing: -0.3px;
    }
    .day-meta {
        font-size: 9px;
        color: #64748B;
        font-weight: 500;
    }
    .day-empty {
        background: transparent;
        border: 1px dashed rgba(255, 255, 255, 0.03);
        border-radius: 8px;
        min-height: 64px;
    }

    /* Minimalist Table */
    .mini-table-box {
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-radius: 10px;
        overflow: hidden;
        background: #0B0E13;
        margin-top: 12px;
    }
    .mini-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 12px;
        text-align: left;
    }
    .mini-table th {
        background: #11151D;
        color: #64748B;
        font-weight: 600;
        text-transform: uppercase;
        font-size: 10px;
        letter-spacing: 0.6px;
        padding: 10px 12px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.07);
    }
    .mini-table td {
        padding: 9px 12px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.03);
        color: #E2E8F0;
        font-family: 'JetBrains Mono', monospace;
        font-size: 11px;
    }
    .mini-table tr:hover {
        background: rgba(255, 255, 255, 0.02);
    }
    .tag-buy {
        color: #34D399;
        font-weight: 700;
    }
    .tag-sell {
        color: #FB7185;
        font-weight: 700;
    }
    .tag-acc {
        color: #94A3B8;
        font-size: 11px;
    }

    /* Minimal Tabs Styling */
    .stTabs [data-baseweb="tab-list"] {
        background: #0E1218 !important;
        border: 1px solid rgba(255, 255, 255, 0.07) !important;
        border-radius: 10px !important;
        padding: 4px !important;
        gap: 4px !important;
        margin-bottom: 18px !important;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 6px !important;
        padding: 6px 14px !important;
        font-size: 12px !important;
        font-weight: 600 !important;
        color: #64748B !important;
        border: none !important;
    }
    .stTabs [aria-selected="true"] {
        background: #181E29 !important;
        color: #F8FAFC !important;
    }

    /* Form Inputs */
    .stTextInput>div>div>input, .stSelectbox>div>div>div {
        background-color: #0E1218 !important;
        border: 1px solid rgba(255, 255, 255, 0.09) !important;
        border-radius: 6px !important;
        color: #F8FAFC !important;
        font-size: 12px !important;
    }
    .stButton>button {
        background: #1E293B !important;
        color: #F8FAFC !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 6px !important;
        padding: 6px 14px !important;
        font-size: 12px !important;
        font-weight: 600 !important;
    }
    .stButton>button:hover {
        background: #334155 !important;
        border-color: rgba(255, 255, 255, 0.2) !important;
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
        
        demo_executions = [
            ("2026-09-28 10:15:00", 18450.0, 22.0, 3, "Topstep_100k_Alpha"),
            ("2026-09-28 14:10:00", 18475.0, 18.0, 3, "Topstep_100k_Alpha"),
            ("2026-09-29 09:50:00", 18510.0, 30.0, 3, "Topstep_100k_Alpha"),
            ("2026-09-29 13:20:00", 18540.0, -8.0, 3, "Topstep_100k_Alpha"),
            ("2026-09-30 10:30:00", 18560.0, 35.0, 3, "Topstep_100k_Alpha"),
            ("2026-09-30 14:40:00", 18595.0, 25.0, 3, "Topstep_100k_Alpha"),
            ("2026-10-01 10:14:00", 18485.0, 24.0, 3, "Topstep_100k_Alpha"),
            ("2026-10-01 14:25:00", 18512.0, 18.5, 3, "Topstep_100k_Alpha"),
            ("2026-10-02 09:45:00", 18530.0, 31.0, 3, "Topstep_100k_Alpha"),
            ("2026-10-02 13:10:00", 18575.0, -8.0, 3, "Topstep_100k_Alpha"),
            ("2026-10-05 10:30:00", 18590.0, 28.5, 3, "Topstep_100k_Alpha"),
            ("2026-10-05 11:45:00", 18625.0, 34.0, 3, "Topstep_100k_Alpha"),
            ("2026-10-05 14:50:00", 18660.0, 14.0, 3, "Topstep_100k_Alpha"),
            ("2026-10-06 10:15:00", 18680.0, 42.0, 3, "Topstep_100k_Alpha"),
            ("2026-10-06 13:40:00", 18730.0, -6.5, 3, "Topstep_100k_Alpha"),
            ("2026-10-07 09:50:00", 18710.0, 38.0, 3, "Topstep_100k_Alpha"),
            ("2026-10-07 11:20:00", 18755.0, 26.5, 3, "Topstep_100k_Alpha"),
            ("2026-10-07 14:15:00", 18790.0, 19.5, 3, "Topstep_100k_Alpha"),
            ("2026-10-08 10:10:00", 18810.0, -12.0, 3, "Topstep_100k_Alpha"),
            ("2026-10-08 13:30:00", 18785.0, -7.0, 3, "Topstep_100k_Alpha"),
            ("2026-10-09 09:40:00", 18760.0, 45.0, 3, "Topstep_100k_Alpha"),
            ("2026-10-09 11:15:00", 18815.0, 32.0, 3, "Topstep_100k_Alpha"),
            ("2026-10-09 14:30:00", 18850.0, 22.5, 3, "Topstep_100k_Alpha"),
            ("2026-10-12 10:00:00", 18880.0, 28.0, 3, "Topstep_100k_Alpha"),
            ("2026-10-12 11:45:00", 18915.0, 36.5, 3, "Topstep_100k_Alpha"),
        ]
        for t_time, entry_p, pts, qty, acc in demo_executions:
            pnl_usd = pts * 2.0 * qty
            exit_p = entry_p + pts
            c.execute('''INSERT INTO trades 
                         (account_name, trade_time, asset, side, entry_price, exit_price, pnl_points, pnl_usd, contracts, execution_type)
                         VALUES (?, ?, 'MNQ', 'BUY', ?, ?, ?, ?, ?, 'LIVE_RTH')''',
                      (acc, t_time, entry_p, exit_p, pts, pnl_usd, qty))
        conn.commit()
    conn.close()

seed_demo_data_if_empty()

# Singletons
if "strategy" not in st.session_state:
    st.session_state.strategy = PureRTHEquilibriumStrategyEngine(asset="MNQ")
if "risk" not in st.session_state:
    st.session_state.risk = RiskManagementEngine(asset="MNQ")
if "router" not in st.session_state:
    st.session_state.router = BrokerMultiAccountRouter(asset="MNQ")

# ----------------- MINIMAL TOPBAR -----------------
accounts_df = get_accounts()
active_count = len(accounts_df[accounts_df['is_active'] == 1]) if not accounts_df.empty else 0

st.markdown(f"""
<div class="nav-minimal">
    <div class="nav-left">
        <span class="nav-brand">⚡ EQUILIBRIUM</span>
        <span class="nav-sub">/ FUNDED TERMINAL</span>
    </div>
    <div class="nav-right">
        <span class="nav-tag">MNQ 09:30–15:55 EST</span>
        <span class="nav-tag">{active_count} Linked</span>
        <span class="nav-status"><span class="dot-live"></span> ACTIVE</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ----------------- NAVIGATION TABS -----------------
tab_dash, tab_strat, tab_acc, tab_audit = st.tabs([
    "📈 Performance & Funded Hub",
    "⚡ Strategy Mechanics",
    "🔑 Multi-Account Router",
    "📜 Trade Statement"
])

# ================= TAB 1: MINIMALIST PERFORMANCE & FUNDED HUB =================
with tab_dash:
    trades_df = get_trades_df()
    
    if trades_df.empty:
        st.info("No executions recorded yet. Add an account or simulate trades in Tab 2.")
    else:
        # Minimalist Inline Toolbar
        c_acc, c_prop, c_space = st.columns([1.5, 2.2, 0.3])
        with c_acc:
            acc_list = ["ALL PORTFOLIOS (AGGREGATED)"] + trades_df['account_name'].unique().tolist()
            selected_acc = st.selectbox("Portfolio Filter", acc_list, label_visibility="collapsed")
            
        with c_prop:
            prop_preset = st.selectbox("Target Preset", [
                "Topstep 100k Combine ($6,000 Target | $3k Trailing DD)",
                "Apex 100k Evaluation ($6,000 Target | $3k Trailing DD)",
                "Topstep 50k Combine ($3,000 Target | $2k Trailing DD)",
                "Apex 50k Evaluation ($3,000 Target | $2.5k Trailing DD)",
                "Custom Rules..."
            ], label_visibility="collapsed")

        # Preset Values
        if "50k" in prop_preset:
            initial_balance, profit_target = 50000.0, 3000.0
            max_trailing_dd = 2000.0 if "Topstep" in prop_preset else 2500.0
            daily_loss_limit, min_days = 1000.0, 5
        elif "Custom" in prop_preset:
            with st.expander("⚙️ Custom Rules Configuration", expanded=False):
                cr1, cr2, cr3, cr4 = st.columns(4)
                initial_balance = cr1.number_input("Starting ($)", value=100000.0, step=10000.0)
                profit_target = cr2.number_input("Target ($)", value=6000.0, step=500.0)
                max_trailing_dd = cr3.number_input("Max DD ($)", value=3000.0, step=500.0)
                daily_loss_limit = cr4.number_input("Daily Loss ($)", value=2000.0, step=500.0)
                min_days = 5
        else:
            initial_balance, profit_target = 100000.0, 6000.0
            max_trailing_dd, daily_loss_limit, min_days = 3000.0, 2000.0, 5

        # Filter View DataFrame
        df_view = trades_df.copy()
        if selected_acc != "ALL PORTFOLIOS (AGGREGATED)":
            df_view = df_view[df_view['account_name'] == selected_acc]
            
        df_view = df_view.sort_values(by='trade_time', ascending=True).reset_index(drop=True)
        df_view['cum_pnl'] = df_view['pnl_usd'].cumsum()
        df_view['peak'] = df_view['cum_pnl'].cummax()
        df_view['drawdown_usd'] = df_view['cum_pnl'] - df_view['peak']
        
        # Financial Quant Metrics
        total_pnl = float(df_view['pnl_usd'].sum())
        total_trades = len(df_view)
        wins = len(df_view[df_view['pnl_usd'] > 0])
        win_rate = (wins / total_trades * 100.0) if total_trades > 0 else 0.0
        
        gp = df_view[df_view['pnl_usd'] > 0]['pnl_usd'].sum()
        gl = abs(df_view[df_view['pnl_usd'] <= 0]['pnl_usd'].sum())
        profit_factor = (gp / gl) if gl > 0 else (99.9 if gp > 0 else 0.0)
        max_dd = float(df_view['drawdown_usd'].min())

        # Funded Math
        current_equity = initial_balance + total_pnl
        target_progress_pct = max(0.0, min(100.0, (total_pnl / profit_target * 100.0))) if profit_target > 0 else 100.0
        remaining_target = max(0.0, profit_target - total_pnl)
        
        running_equity = initial_balance + df_view['cum_pnl']
        hwm = max(initial_balance, float(running_equity.max()))
        liquidation_threshold = hwm - max_trailing_dd
        trailing_buffer_remaining = max(0.0, current_equity - liquidation_threshold)
        trailing_buffer_pct = max(0.0, min(100.0, (trailing_buffer_remaining / max_trailing_dd * 100.0)))

        today_str = datetime.date.today().strftime('%Y-%m-%d')
        df_view['date_str'] = df_view['trade_time'].dt.strftime('%Y-%m-%d')
        today_trades = df_view[df_view['date_str'] == today_str]
        today_pnl = float(today_trades['pnl_usd'].sum()) if not today_trades.empty else 0.0
        daily_consumed = abs(today_pnl) if today_pnl < 0 else 0.0
        daily_buffer_remaining = max(0.0, daily_loss_limit - daily_consumed)
        daily_buffer_pct = max(0.0, min(100.0, (daily_buffer_remaining / daily_loss_limit * 100.0)))

        days_traded = df_view['trade_time'].dt.date.nunique()
        day_pnl_series = df_view.groupby(df_view['trade_time'].dt.date)['pnl_usd'].sum()
        best_day_pnl = float(day_pnl_series.max()) if not day_pnl_series.empty else 0.0
        consistency_pct = (best_day_pnl / total_pnl * 100.0) if total_pnl > 0 and best_day_pnl > 0 else 0.0

        # UNIFIED MINIMALIST 5-KPI METRIC STRIP
        dd_fill = "micro-fill-emerald" if trailing_buffer_pct > 50 else ("micro-fill-amber" if trailing_buffer_pct > 25 else "micro-fill-rose")

        st.markdown(f"""
        <div class="kpi-row">
            <div class="kpi-card">
                <div class="kpi-header">
                    <span>Account Balance</span>
                    <span>💵</span>
                </div>
                <div class="kpi-value">${current_equity:,.2f}</div>
                <div class="kpi-sub" style="color: {'#34D399' if total_pnl >= 0 else '#FB7185'};">
                    {'+' if total_pnl >= 0 else ''}${total_pnl:,.2f} ({'+' if total_pnl >= 0 else ''}{(total_pnl/initial_balance*100):.2f}%)
                </div>
            </div>
            <div class="kpi-card">
                <div class="kpi-header">
                    <span>Profit Target</span>
                    <span>🎯</span>
                </div>
                <div class="kpi-value">${remaining_target:,.2f} <span style="font-size: 11px; color: #64748B; font-weight: 500;">left</span></div>
                <div class="micro-progress">
                    <div class="micro-fill-sky" style="width: {target_progress_pct:.1f}%;"></div>
                </div>
                <div class="kpi-sub">
                    <span>{target_progress_pct:.1f}%</span> • <span>Target ${profit_target:,.0f}</span>
                </div>
            </div>
            <div class="kpi-card">
                <div class="kpi-header">
                    <span>Trailing DD Buffer</span>
                    <span>🛡️</span>
                </div>
                <div class="kpi-value" style="color: {'#34D399' if trailing_buffer_remaining > 1000 else '#FBBF24'};">
                    ${trailing_buffer_remaining:,.2f}
                </div>
                <div class="micro-progress">
                    <div class="{dd_fill}" style="width: {trailing_buffer_pct:.1f}%;"></div>
                </div>
                <div class="kpi-sub">
                    <span>Floor: ${liquidation_threshold:,.2f}</span>
                </div>
            </div>
            <div class="kpi-card">
                <div class="kpi-header">
                    <span>Today's Realized</span>
                    <span>⚡</span>
                </div>
                <div class="kpi-value" style="color: {'#34D399' if today_pnl >= 0 else '#FB7185'};">
                    {'+' if today_pnl >= 0 else ''}${today_pnl:,.2f}
                </div>
                <div class="kpi-sub">
                    <span>Buffer: ${daily_buffer_remaining:,.0f} safe</span>
                </div>
            </div>
            <div class="kpi-card">
                <div class="kpi-header">
                    <span>Discipline & Stats</span>
                    <span>⚖️</span>
                </div>
                <div class="kpi-value">{win_rate:.1f}% <span style="font-size: 11px; color: #64748B; font-weight: 500;">Win</span></div>
                <div class="kpi-sub">
                    <span>PF {profit_factor:.2f}</span> • <span>{days_traded}d</span> • <span>MaxDay {consistency_pct:.1f}%</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # CUMULATIVE EQUITY PERFORMANCE CHART
        st.markdown("""
        <div class="panel-box">
            <div class="panel-top">
                <span class="panel-heading">Equity Progression</span>
                <span class="panel-meta">New York RTH Sessions • Zero Overnight Exposure</span>
            </div>
        """, unsafe_allow_html=True)
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_view['trade_time'],
            y=df_view['cum_pnl'],
            mode='lines',
            name='Equity ($)',
            line=dict(color='#10B981', width=1.75),
            fill='tozeroy',
            fillcolor='rgba(16, 185, 129, 0.05)'
        ))
        fig.update_layout(
            template='plotly_dark',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            height=280,
            margin=dict(l=5, r=5, t=5, b=5),
            xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.03)', color='#64748B', zeroline=False),
            yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.03)', color='#64748B', tickprefix="$", zeroline=False),
            hovermode="x unified"
        )
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

        # MINIMALIST MONTHLY CALENDAR PROFITS HEATMAP
        df_view['year'] = df_view['trade_time'].dt.year
        df_view['month'] = df_view['trade_time'].dt.month
        available_months = df_view[['year', 'month']].drop_duplicates().sort_values(by=['year', 'month'], ascending=False)
        month_options = [f"{datetime.date(r.year, r.month, 1).strftime('%B %Y')}" for _, r in available_months.iterrows()]

        st.markdown("""
        <div class="panel-box">
            <div class="panel-top">
                <span class="panel-heading">Monthly Calendar Profits</span>
                <span class="panel-meta">Daily Realized Cash Heatmap</span>
            </div>
        """, unsafe_allow_html=True)

        c_c1, c_c2 = st.columns([1.5, 3])
        with c_c1:
            sel_m_label = st.selectbox("Calendar Month", month_options, index=0, label_visibility="collapsed")
            sel_dt = datetime.datetime.strptime(sel_m_label, "%B %Y")
            cal_year, cal_month = sel_dt.year, sel_dt.month

        df_month = df_view[(df_view['year'] == cal_year) & (df_view['month'] == cal_month)].copy()
        daily_stats = {}
        if not df_month.empty:
            df_month['day_str'] = df_month['trade_time'].dt.strftime('%Y-%m-%d')
            for d_str, grp in df_month.groupby('day_str'):
                daily_stats[d_str] = {
                    'pnl': float(grp['pnl_usd'].sum()),
                    'count': len(grp),
                    'wins': int((grp['pnl_usd'] > 0).sum()),
                    'losses': int((grp['pnl_usd'] <= 0).sum())
                }

        m_total_pnl = sum(s['pnl'] for s in daily_stats.values()) if daily_stats else 0.0
        m_days_count = len(daily_stats)
        m_win_days = sum(1 for s in daily_stats.values() if s['pnl'] > 0)
        m_loss_days = sum(1 for s in daily_stats.values() if s['pnl'] < 0)
        m_win_rate = (m_win_days / m_days_count * 100.0) if m_days_count > 0 else 0.0
        m_best_day = max((s['pnl'] for s in daily_stats.values()), default=0.0)

        with c_c2:
            st.markdown(f"""
            <div style="display: flex; justify-content: flex-end; gap: 18px; align-items: center; font-size: 12px; padding-top: 6px;">
                <span>Month: <b style="color: {'#34D399' if m_total_pnl >= 0 else '#FB7185'};">{'+' if m_total_pnl >= 0 else ''}${m_total_pnl:,.2f}</b></span>
                <span>Days: <b>{m_days_count}d</b></span>
                <span>Win Days: <b style="color: #38BDF8;">{m_win_rate:.0f}%</b> ({m_win_days}W / {m_loss_days}L)</span>
                <span>Best: <b style="color: #34D399;">+${m_best_day:,.2f}</b></span>
            </div>
            """, unsafe_allow_html=True)

        # 7-Column Minimalist Grid
        weekdays_html = "".join([f'<div class="cal-weekday-th">{d}</div>' for d in ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]])
        st.markdown(f'<div class="cal-weekdays">{weekdays_html}</div>', unsafe_allow_html=True)

        cal_matrix = calendar.monthcalendar(cal_year, cal_month)
        days_cells_html = []
        for week in cal_matrix:
            for day_idx, day_num in enumerate(week):
                if day_num == 0:
                    days_cells_html.append('<div class="day-empty"></div>')
                else:
                    date_key = f"{cal_year}-{cal_month:02d}-{day_num:02d}"
                    if date_key in daily_stats:
                        st_day = daily_stats[date_key]
                        p_val = st_day['pnl']
                        c_cls = "day-green" if p_val > 0 else ("day-red" if p_val < 0 else "")
                        sign = "+" if p_val > 0 else ""
                        color = "#34D399" if p_val > 0 else ("#FB7185" if p_val < 0 else "#94A3B8")
                        days_cells_html.append(f"""
                        <div class="day-box {c_cls}">
                            <div class="day-num">{day_num:02d}</div>
                            <div class="day-pnl" style="color: {color};">{sign}${p_val:,.2f}</div>
                            <div class="day-meta">{st_day['count']} trades</div>
                        </div>
                        """)
                    else:
                        is_weekend = (day_idx >= 5)
                        sub = "Closed" if is_weekend else "—"
                        days_cells_html.append(f"""
                        <div class="day-box">
                            <div class="day-num" style="opacity: 0.4;">{day_num:02d}</div>
                            <div class="day-pnl" style="color: #334155; font-size: 11px;">—</div>
                            <div class="day-meta" style="opacity: 0.4;">{sub}</div>
                        </div>
                        """)

        st.markdown(f'<div class="cal-grid">{"".join(days_cells_html)}</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        # MINIMALIST TRADE HISTORY DOCKED AT THE BOTTOM
        st.markdown("""
        <div class="panel-box">
            <div class="panel-top">
                <span class="panel-heading">Trade Executions</span>
                <span class="panel-meta">Audited Live Fills Ledger</span>
            </div>
        """, unsafe_allow_html=True)

        # Clean Inline Filter Bar
        cf_res, cf_side, cf_rows, cf_down = st.columns([1.5, 1.2, 1.2, 1.2])
        with cf_res:
            f_res = st.selectbox("Filter", ["All Trades", "Winners Only (🟢)", "Losers Only (🔴)"], label_visibility="collapsed")
        with cf_side:
            f_side = st.selectbox("Side", ["All Sides", "BUY Only", "SELL Only"], label_visibility="collapsed")
        with cf_rows:
            f_rows = st.selectbox("Rows", ["Last 15", "Last 30", "Last 50", "All Trades"], label_visibility="collapsed")

        df_hist = df_view.sort_values(by='trade_time', ascending=False).copy()
        if "Winners" in f_res:
            df_hist = df_hist[df_hist['pnl_usd'] > 0]
        elif "Losers" in f_res:
            df_hist = df_hist[df_hist['pnl_usd'] <= 0]
            
        if "BUY" in f_side:
            df_hist = df_hist[df_hist['side'] == 'BUY']
        elif "SELL" in f_side:
            df_hist = df_hist[df_hist['side'] == 'SELL']

        if "15" in f_rows:
            df_hist_sub = df_hist.head(15)
        elif "30" in f_rows:
            df_hist_sub = df_hist.head(30)
        elif "50" in f_rows:
            df_hist_sub = df_hist.head(50)
        else:
            df_hist_sub = df_hist

        with cf_down:
            csv_d = df_hist.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Export CSV",
                data=csv_d,
                file_name=f"trades_{datetime.date.today()}.csv",
                mime="text/csv",
                use_container_width=True
            )

        # Clean Table Rows
        rows_html = []
        for _, r in df_hist_sub.iterrows():
            t_s = r['trade_time'].strftime('%Y-%m-%d %H:%M:%S')
            side_tag = '<span class="tag-buy">BUY</span>' if r['side'] == 'BUY' else '<span class="tag-sell">SELL</span>'
            p_val = r['pnl_usd']
            p_pts = r['pnl_points']
            p_col = "#34D399" if p_val >= 0 else "#FB7185"
            sign = "+" if p_val >= 0 else ""
            
            rows_html.append(f"""
            <tr>
                <td style="color: #64748B;">{t_s}</td>
                <td><span class="tag-acc">{r['account_name']}</span></td>
                <td style="color: #CBD5E1; font-weight: 600;">{r['asset']}</td>
                <td>{side_tag}</td>
                <td>{r['entry_price']:.2f}</td>
                <td>{r['exit_price']:.2f}</td>
                <td style="color: {p_col};">{sign}{p_pts:.2f} pts</td>
                <td style="color: {p_col}; font-weight: 700;">{sign}${p_val:,.2f}</td>
                <td style="color: #94A3B8;">{int(r['contracts'])}</td>
                <td style="color: #475569; font-size: 10px;">{r['execution_type']}</td>
            </tr>
            """)

        st.markdown(f"""
        <div class="mini-table-box">
            <table class="mini-table">
                <thead>
                    <tr>
                        <th>Time (EST)</th>
                        <th>Account</th>
                        <th>Asset</th>
                        <th>Side</th>
                        <th>Entry</th>
                        <th>Exit</th>
                        <th>Points</th>
                        <th>Net Realized</th>
                        <th>Qty</th>
                        <th>Engine</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(rows_html)}
                </tbody>
            </table>
        </div>
        """, unsafe_allow_html=True)

        h_pts = df_hist_sub['pnl_points'].sum()
        h_usd = df_hist_sub['pnl_usd'].sum()
        h_w = len(df_hist_sub[df_hist_sub['pnl_usd'] > 0])
        h_r = (h_w / len(df_hist_sub) * 100.0) if len(df_hist_sub) > 0 else 0.0

        st.markdown(f"""
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 10px; font-size: 11px; color: #64748B;">
            <div>Showing <b>{len(df_hist_sub)}</b> of {len(df_hist)} executions</div>
            <div style="display: flex; gap: 16px;">
                <span>Win Rate: <b style="color: #38BDF8;">{h_r:.1f}%</b> ({h_w}/{len(df_hist_sub)})</span>
                <span>Points: <b style="color: {'#34D399' if h_pts >= 0 else '#FB7185'};">{'+' if h_pts >= 0 else ''}{h_pts:.2f} pts</b></span>
                <span>Net: <b style="color: {'#34D399' if h_usd >= 0 else '#FB7185'};">{'+' if h_usd >= 0 else ''}${h_usd:,.2f}</b></span>
            </div>
        </div>
        </div>
        """, unsafe_allow_html=True)


# ================= TAB 2: STRATEGY & SIMULATION =================
with tab_strat:
    strat = st.session_state.strategy
    risk = st.session_state.risk
    stat = strat.get_status()
    
    st.markdown("""
    <div class="panel-box">
        <div class="panel-top">
            <span class="panel-heading">Wave Mechanics & Live State</span>
            <span class="panel-meta">Audited 4-State Cycle tracking Anchor, Peak, and 50% Equilibrium touch</span>
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
            st.markdown(f"**Trailing SL Engaged:** `{'YES' if risk.sl_moved else 'NO'}`")
        else:
            st.markdown("*Awaiting next 50% retracement.*")
    with c_s3:
        st.markdown("##### 🚀 Execution Rules")
        st.markdown(f"**Instrument:** `{strat.asset}`")
        st.markdown(f"**Model:** `Immediate Market Order`")
        st.markdown(f"**Slippage Penalty:** `2 Ticks (0.50 pts absorbed)`")
        st.markdown(f"**EOD Liquidator:** `15:59 EST Hard Flatten`")
        
    st.markdown("---")
    st.markdown("##### 🕹️ Pipeline Simulator")
    
    sim_c1, sim_c2, sim_c3 = st.columns(3)
    if sim_c1.button("1. 🔔 09:30 AM Opening Bell"):
        strat.reset_at_open(18530.0, 18500.0)
        st.success("Slate wiped. Anchor = 18500.0, Peak = 18530.0.")
        
    if sim_c2.button("2. 📉 Impulse & 50% Touch Entry"):
        strat.day_low = 18500.0
        strat.bull_anchor = 18500.0
        strat.bull_extreme = 18550.0
        strat.bull_state = 3
        strat.active_bias = "BULL"
        
        sig = strat.process_bar(18535.0, 18524.5, 18530.0, is_entry_allowed=True)
        if sig:
            risk.open_position(sig)
            st.session_state.router.dispatch_entry(sig)
            st.success(f"50% Touch filled at {sig['entry_price']:.2f}. SL at {sig['sl_price']:.2f}.")
            
    if sim_c3.button("3. 🎯 Take Profit Reached"):
        if risk.in_trade:
            tp = risk.tp_price
            exit_ev = risk.evaluate_bar(tp + 2.0, tp - 2.0, tp)
            if exit_ev:
                st.session_state.router.dispatch_exit(exit_ev, risk.side, risk.entry_price)
                st.success(f"Take Profit reached (+{exit_ev['pnl_points']:.2f} pts). Recorded in DB!")
        else:
            st.warning("Position is flat. Click Button 2 first!")
            
    st.markdown("</div>", unsafe_allow_html=True)


# ================= TAB 3: MULTI-ACCOUNT ROUTER =================
with tab_acc:
    st.markdown("""
    <div class="panel-box">
        <div class="panel-top">
            <span class="panel-heading">Multi-Account API Management</span>
            <span class="panel-meta">Concurrent Order Dispatcher</span>
        </div>
    """, unsafe_allow_html=True)
    
    accs = get_accounts()
    if not accs.empty:
        st.dataframe(
            accs[['id', 'account_name', 'broker', 'contracts', 'is_active', 'created_at']],
            use_container_width=True
        )
        
        c_act1, c_act2, c_act3 = st.columns([1, 1, 2])
        target_id = c_act1.number_input("Account ID", min_value=1, step=1, label_visibility="collapsed")
        if c_act2.button("Toggle Status"):
            curr = accs[accs['id'] == target_id]['is_active'].values
            if len(curr) > 0:
                toggle_account_status(target_id, 0 if curr[0] == 1 else 1)
                st.rerun()
        if c_act3.button("Delete Connection"):
            delete_account(target_id)
            st.rerun()
    else:
        st.info("No accounts linked yet.")
        
    st.markdown("---")
    st.markdown("##### Link New Account")
    with st.form("add_acc_form"):
        col_f1, col_f2 = st.columns(2)
        acc_n = col_f1.text_input("Account Identifier", placeholder="Topstep_100k_Combine_02")
        brk_t = col_f2.selectbox("Broker Feed", [
            "Topstep (Tradovate)", "Apex Trader Funding", "Tradovate Live API", "NinjaTrader 8 (Local)", "Interactive Brokers"
        ])
        col_f3, col_f4 = st.columns(2)
        a_key = col_f3.text_input("API Key / Username", type="password")
        a_sec = col_f4.text_input("API Secret / Password", type="password")
        c_qty = st.slider("Position Size (Contracts)", min_value=1, max_value=20, value=3)
        
        if st.form_submit_button("Authorise & Link"):
            if acc_n and a_key:
                add_account(acc_n, brk_t, a_key, a_sec, c_qty)
                st.success(f"Account '{acc_n}' linked!")
                st.rerun()
            else:
                st.error("Provide Account Name and API Key.")
    st.markdown("</div>", unsafe_allow_html=True)


# ================= TAB 4: TRADE STATEMENT =================
with tab_audit:
    st.markdown("""
    <div class="panel-box">
        <div class="panel-top">
            <span class="panel-heading">Trade Audit Statement</span>
            <span class="panel-meta">Cryptographic Execution Ledger</span>
        </div>
    """, unsafe_allow_html=True)
    
    all_trades = get_trades_df()
    if not all_trades.empty:
        csv_bytes = all_trades.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Export Full Statement (.CSV)",
            data=csv_bytes,
            file_name=f"statement_{datetime.date.today()}.csv",
            mime="text/csv"
        )
        st.dataframe(all_trades, use_container_width=True)
    else:
        st.info("No records found.")
    st.markdown("</div>", unsafe_allow_html=True)
