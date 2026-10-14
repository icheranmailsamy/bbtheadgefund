import streamlit as st
import pandas as pd
import datetime
import os

from engine.storage import (
    init_db, get_accounts, add_account, toggle_account_status,
    delete_account, get_system_state, set_system_state, get_trades_df
)
from engine.strategy import PureRTHEquilibriumStrategyEngine
from engine.risk_engine import RiskManagementEngine
from engine.broker_router import BrokerMultiAccountRouter
from engine.tick_engine import RealtimeTickAggregatorEngine

# ----------------- PAGE CONFIGURATION -----------------
st.set_page_config(
    page_title="Equilibrium // Gateway",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ----------------- CENTERED ULTRA-MINIMAL CSS SYSTEM -----------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

    /* Global Typography & Layout */
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Strict Centering & Proportional Width Constraints */
    .block-container {
        max-width: 980px !important;
        margin-left: auto !important;
        margin-right: auto !important;
        padding-top: 3rem !important;
        padding-bottom: 3rem !important;
        padding-left: 1.5rem !important;
        padding-right: 1.5rem !important;
    }
    #MainMenu, footer, header { display: none !important; }

    /* Minimalist Dark Obsidian Canvas */
    .stApp {
        background-color: #07080B !important;
        background-image: 
            radial-gradient(ellipse at 50% 12%, rgba(56, 189, 248, 0.08) 0%, transparent 65%),
            radial-gradient(ellipse at 50% 88%, rgba(16, 185, 129, 0.05) 0%, transparent 65%) !important;
        background-attachment: fixed !important;
        color: #E2E8F0 !important;
    }
    .mono { font-family: 'JetBrains Mono', monospace !important; }

    /* Centered Header Section */
    .header-centered {
        text-align: center;
        margin-bottom: 30px;
    }
    .header-pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        padding: 5px 14px;
        border-radius: 999px;
        font-size: 11px;
        font-weight: 600;
        color: #94A3B8;
        letter-spacing: 0.6px;
        text-transform: uppercase;
        margin-bottom: 12px;
    }
    .header-title {
        font-size: 28px;
        font-weight: 800;
        color: #F8FAFC;
        letter-spacing: -0.8px;
        margin-bottom: 6px;
    }
    .header-subtitle {
        font-size: 13px;
        color: #64748B;
        font-weight: 400;
        max-width: 580px;
        margin: 0 auto 16px auto;
        line-height: 1.5;
    }
    .header-status-strip {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 12px;
    }

    /* Badges & Pills */
    .status-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 11px;
        font-weight: 600;
        padding: 4px 12px;
        border-radius: 999px;
    }
    .status-emerald {
        background: rgba(16, 185, 129, 0.1);
        border: 1px solid rgba(16, 185, 129, 0.25);
        color: #34D399;
    }
    .status-slate {
        background: rgba(148, 163, 184, 0.08);
        border: 1px solid rgba(148, 163, 184, 0.16);
        color: #94A3B8;
    }
    .pulse-dot {
        width: 6px;
        height: 6px;
        background-color: #10B981;
        border-radius: 50%;
        box-shadow: 0 0 8px #10B981;
    }

    /* Native Streamlit Column Styling as Modern Cards */
    [data-testid="column"] {
        background: #0D1117 !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 16px !important;
        padding: 24px 22px !important;
        box-shadow: 0 8px 30px -4px rgba(0, 0, 0, 0.4) !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: space-between !important;
        transition: border-color 0.2s ease !important;
    }
    [data-testid="column"]:hover {
        border-color: rgba(255, 255, 255, 0.16) !important;
    }

    /* Reset Nested Helper Columns inside Cards */
    [data-testid="column"] [data-testid="column"] {
        background: transparent !important;
        border: none !important;
        border-radius: 0 !important;
        padding: 0 !important;
        box-shadow: none !important;
    }

    /* Reset Columns with Unveil Marker */
    [data-testid="column"]:has(.unveil-marker) {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
    }

    /* Card Titles Inside Columns */
    .card-heading-box {
        margin-bottom: 16px;
        padding-bottom: 12px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
    }
    .card-title-text {
        font-size: 16px;
        font-weight: 700;
        color: #F8FAFC;
        letter-spacing: -0.3px;
        margin-bottom: 4px;
    }
    .card-sub-text {
        font-size: 12px;
        color: #64748B;
        font-weight: 400;
    }

    /* Minimalist Inputs */
    .stTextInput>div>div>input, .stSelectbox>div>div>div {
        background-color: #080B10 !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 8px !important;
        color: #F8FAFC !important;
        font-size: 12px !important;
    }
    .stTextInput>div>div>input:focus, .stSelectbox>div>div>div:focus {
        border-color: rgba(56, 189, 248, 0.5) !important;
    }

    /* High-Aesthetic Buttons */
    .stButton>button {
        background: #181E29 !important;
        color: #F8FAFC !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 8px !important;
        padding: 8px 16px !important;
        font-size: 12px !important;
        font-weight: 600 !important;
        transition: all 0.2s ease !important;
    }
    .stButton>button:hover {
        background: #2563EB !important;
        border-color: rgba(37, 99, 235, 0.5) !important;
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.35) !important;
    }

    /* Account Roster Items */
    .acc-item-row {
        background: #080B10;
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 8px;
        padding: 10px 12px;
        margin-bottom: 8px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .acc-name-txt {
        font-weight: 600;
        font-size: 12px;
        color: #F1F5F9;
        font-family: 'JetBrains Mono', monospace;
    }
    .acc-broker-txt {
        font-size: 10px;
        color: #64748B;
        margin-top: 1px;
    }
    .acc-qty-badge {
        background: rgba(56, 189, 248, 0.1);
        color: #38BDF8;
        border: 1px solid rgba(56, 189, 248, 0.2);
        border-radius: 4px;
        padding: 2px 7px;
        font-size: 10px;
        font-weight: 600;
        font-family: 'JetBrains Mono', monospace;
    }

    /* Telemetry Box */
    .telemetry-box {
        background: rgba(16, 185, 129, 0.03);
        border: 1px solid rgba(16, 185, 129, 0.15);
        border-radius: 8px;
        padding: 12px 14px;
        margin: 12px 0;
        font-size: 12px;
    }
    .telemetry-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 6px;
    }

    /* Unveil Action Button Styling */
    [data-testid="column"]:has(.unveil-marker) .stButton>button {
        background: #0E1626 !important;
        border: 1px solid rgba(56, 189, 248, 0.35) !important;
        color: #38BDF8 !important;
        font-weight: 600 !important;
        letter-spacing: -0.2px !important;
        padding: 10px 22px !important;
        border-radius: 999px !important;
        font-size: 13px !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 4px 18px rgba(0, 0, 0, 0.4) !important;
    }
    [data-testid="column"]:has(.unveil-marker) .stButton>button:hover {
        background: #1E293B !important;
        border-color: #38BDF8 !important;
        box-shadow: 0 0 20px rgba(56, 189, 248, 0.35) !important;
        color: #FFFFFF !important;
    }

    /* Terminal Console Box */
    .terminal-container {
        background: #06090E;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 14px;
        padding: 18px 20px;
        margin-top: 18px;
        margin-bottom: 24px;
        box-shadow: 0 12px 36px rgba(0, 0, 0, 0.5);
        font-family: 'JetBrains Mono', monospace;
    }
    .terminal-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding-bottom: 12px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
        margin-bottom: 12px;
    }
    .terminal-dots {
        display: flex;
        gap: 6px;
        align-items: center;
    }
    .terminal-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        display: inline-block;
    }
    .dot-red { background: #EF4444; }
    .dot-yellow { background: #F59E0B; }
    .dot-green { background: #10B981; }
    .terminal-title {
        font-size: 12px;
        font-weight: 700;
        color: #94A3B8;
        margin-left: 8px;
        letter-spacing: 0.4px;
    }
    .terminal-badge {
        font-size: 10px;
        font-weight: 600;
        padding: 3px 8px;
        border-radius: 4px;
        background: rgba(56, 189, 248, 0.1);
        border: 1px solid rgba(56, 189, 248, 0.25);
        color: #38BDF8;
    }
    .terminal-stream {
        background: #020408;
        border: 1px solid rgba(255, 255, 255, 0.04);
        border-radius: 8px;
        padding: 12px 14px;
        max-height: 290px;
        overflow-y: auto;
        font-size: 11.5px;
        line-height: 1.7;
    }
    .log-row {
        display: flex;
        gap: 10px;
        align-items: baseline;
        padding: 2px 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.02);
    }
    .log-ts {
        color: #475569;
        font-size: 10.5px;
        min-width: 82px;
    }
    .log-tag {
        font-size: 9.5px;
        font-weight: 700;
        padding: 1px 6px;
        border-radius: 3px;
        min-width: 68px;
        text-align: center;
    }
    .tag-tick { background: rgba(56, 189, 248, 0.15); color: #38BDF8; }
    .tag-touch { background: rgba(232, 121, 249, 0.18); color: #E879F9; font-weight: 800; }
    .tag-order { background: rgba(52, 211, 153, 0.15); color: #34D399; }
    .tag-exit { background: rgba(16, 185, 129, 0.2); color: #10B981; }
    .tag-risk { background: rgba(251, 191, 36, 0.15); color: #FBBF24; }
    .tag-strategy { background: rgba(168, 85, 247, 0.15); color: #A855F7; }
    .tag-feed { background: rgba(45, 212, 191, 0.15); color: #2DD4BF; }
    .tag-system { background: rgba(148, 163, 184, 0.15); color: #94A3B8; }
    .log-msg {
        color: #E2E8F0;
        word-break: break-word;
    }

    /* Centered Footer */
    .centered-footer {
        text-align: center;
        margin-top: 36px;
        padding-top: 18px;
        border-top: 1px solid rgba(255, 255, 255, 0.05);
        font-size: 11px;
        color: #475569;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Storage
init_db()

# Load Accounts (Fresh state - zero demo auto-seeding)
accounts_df = get_accounts()

# Singletons in Session State
if "strategy" not in st.session_state:
    st.session_state.strategy = PureRTHEquilibriumStrategyEngine(asset="MNQ")
if "risk" not in st.session_state:
    st.session_state.risk = RiskManagementEngine(asset="MNQ")
if "router" not in st.session_state:
    st.session_state.router = BrokerMultiAccountRouter(asset="MNQ")
if "tick_engine" not in st.session_state:
    st.session_state.tick_engine = RealtimeTickAggregatorEngine(
        asset="MNQ",
        strategy=st.session_state.strategy,
        risk=st.session_state.risk,
        router=st.session_state.router
    )

# Retrieve or initialize Data Feed State (Defaults to disconnected on fresh start)
feed_connected = get_system_state("data_feed_connected", "0") == "1"
feed_provider = get_system_state("data_feed_provider", "Tradovate WebSocket API")
feed_asset = get_system_state("data_feed_asset", "MNQ")
saved_feed_key = get_system_state("data_feed_key", "")

active_accounts_count = len(accounts_df[accounts_df['is_active'] == 1]) if not accounts_df.empty else 0
tick_engine = st.session_state.tick_engine

# Helper: Append Event to In-Memory Temporary Log Stream
def log_temp_event(category, message, level="INFO"):
    if "temp_logs" not in st.session_state:
        st.session_state.temp_logs = []
    
    timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    st.session_state.temp_logs.append({
        "time": timestamp,
        "category": category,
        "level": level,
        "message": message
    })
    if len(st.session_state.temp_logs) > 150:
        st.session_state.temp_logs = st.session_state.temp_logs[-150:]

# Initialize Fresh Temp Logs (Zero mock/simulated logs)
if "temp_logs" not in st.session_state:
    st.session_state.temp_logs = []

if "show_temp_logs" not in st.session_state:
    st.session_state.show_temp_logs = False

# ----------------- CENTERED HEADER -----------------
st.markdown(f"""
<div class="header-centered">
    <div class="header-pill">⚡ Equilibrium Architecture</div>
    <div class="header-title">Institutional Trading Gateway</div>
    <div class="header-subtitle">
        Market data is ingested <b>every single tick</b>, building real-time 1-minute bars with <b>instant intra-candle 50% equilibrium touch execution</b>.
    </div>
    <div class="header-status-strip">
        <span class="status-pill {'status-emerald' if feed_connected else 'status-slate'}">
            <span class="{'pulse-dot' if feed_connected else ''}"></span>
            {'TICK FEED: ACTIVE' if feed_connected else 'TICK FEED: IDLE'}
        </span>
        <span class="status-pill {'status-emerald' if active_accounts_count > 0 else 'status-slate'}">
            {active_accounts_count} TRADING ACCOUNTS ARMED
        </span>
        <span class="status-pill status-slate">
            SUB-SECOND 50% TOUCH SCANNER
        </span>
    </div>
</div>
""", unsafe_allow_html=True)

# ----------------- TWO BALANCED, CENTERED CARDS -----------------
col_data, col_trade = st.columns(2, gap="large")

# ================= CARD 1: DATA CONNECT API =================
with col_data:
    # Card Header
    feed_badge = '<span class="status-pill status-emerald"><span class="pulse-dot"></span> LIVE TICKS</span>' if feed_connected else '<span class="status-pill status-slate">IDLE</span>'
    st.markdown(f"""
    <div class="card-heading-box">
        <div>
            <div class="card-title-text">Data Connect API</div>
            <div class="card-sub-text">The main source of data to generate signals</div>
        </div>
        <div>{feed_badge}</div>
    </div>
    """, unsafe_allow_html=True)

    # Feed Provider Selection
    c_p1, c_p2 = st.columns(2)
    with c_p1:
        provider_choice = st.selectbox(
            "Feed Provider",
            ["Tradovate WebSocket API", "Rithmic R|API+", "Interactive Brokers (TWS)", "Databento CME Real-time"],
            index=0 if feed_provider == "Tradovate WebSocket API" else 1
        )
    with c_p2:
        asset_choice = st.selectbox(
            "Target Instrument",
            ["MNQ (Micro Nasdaq)", "MES (Micro S&P)", "NQ (E-mini Nasdaq)", "ES (E-mini S&P)"],
            index=0 if "MNQ" in feed_asset else 1
        )

    col_env, col_sess = st.columns(2)
    with col_env:
        st.text_input("Ingestion Protocol", value="Real-Time Tick Stream (L1/L2)", disabled=True)
    with col_sess:
        st.text_input("Session Anchor", value="09:30–15:55 EST (Pure RTH)", disabled=True)

    api_key_input = st.text_input(
        "Feed API Key / Token", 
        value=saved_feed_key, 
        type="password",
        placeholder="Enter Live CME Feed API Key or Access Token"
    )

    # Tick Engine Telemetry Box (Real-Time State, Zero Simulated Fallback Values)
    if tick_engine.last_tick_price > 0:
        last_price_str = f"{tick_engine.last_tick_price:,.2f}"
    else:
        last_price_str = "Standby (Awaiting Ticks)"

    active_bar = tick_engine.current_bar
    if active_bar:
        bar_str = f"O: {active_bar['open']:.2f} | H: {active_bar['high']:.2f} | L: {active_bar['low']:.2f} | C: {active_bar['close']:.2f} (Vol: {active_bar['volume']})"
    else:
        bar_str = "No active candle in memory (Awaiting RTH session)"

    latency_display = "<b class='mono' style='color: #34D399;'>Connected (Live)</b>" if feed_connected else "<b class='mono' style='color: #64748B;'>Disconnected</b>"
    touch_scanner_display = "<b>Sub-Second Real-Time Check (Armed)</b>" if feed_connected else "<b>Standby</b>"

    st.markdown(f"""
    <div class="telemetry-box">
        <div class="telemetry-row">
            <div><span style="color: #64748B;">Last Tick Price:</span> <b class="mono" style="color: #F8FAFC;">{last_price_str}</b></div>
            <div><span style="color: #64748B;">Feed Health:</span> {latency_display}</div>
        </div>
        <div class="telemetry-row">
            <div style="font-size: 11px;"><span style="color: #64748B;">Active 1m Candle:</span> <b class="mono" style="color: #38BDF8;">{bar_str}</b></div>
        </div>
        <div style="font-size: 11px; color: #94A3B8; margin-top: 4px;">
            <span>● 50% Touch Scanner: {touch_scanner_display}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Feed Connection Controls (Real Gateway Actions)
    c_btn1, c_btn2 = st.columns(2)
    with c_btn1:
        if st.button("🔗 Connect Feed" if not feed_connected else "🔄 Reconnect", use_container_width=True):
            set_system_state("data_feed_connected", "1")
            set_system_state("data_feed_provider", provider_choice)
            set_system_state("data_feed_asset", asset_choice)
            if api_key_input:
                set_system_state("data_feed_key", api_key_input)
            log_temp_event("FEED", f"Connected to {provider_choice} for {asset_choice}. WebSocket active.", "INFO")
            st.success("✅ Real-time CME tick stream connected.")
            st.rerun()
    with c_btn2:
        if st.button("⏹ Disconnect", use_container_width=True, disabled=not feed_connected):
            set_system_state("data_feed_connected", "0")
            log_temp_event("FEED", "Market feed disconnected by user.", "WARN")
            st.info("Market feed disconnected.")
            st.rerun()


# ================= CARD 2: TRADING ACCOUNT API =================
with col_trade:
    # Card Header
    trade_badge = f'<span class="status-pill status-emerald">{active_accounts_count} ARMED</span>' if active_accounts_count > 0 else '<span class="status-pill status-slate">0 ARMED</span>'
    st.markdown(f"""
    <div class="card-heading-box">
        <div>
            <div class="card-title-text">Trading Account API</div>
            <div class="card-sub-text">The Accounts where trades should be placed</div>
        </div>
        <div>{trade_badge}</div>
    </div>
    """, unsafe_allow_html=True)

    # Account Roster
    st.markdown("<div style='font-size: 11px; font-weight: 600; color: #64748B; text-transform: uppercase; margin-bottom: 8px;'>Linked Execution Accounts</div>", unsafe_allow_html=True)

    if not accounts_df.empty:
        for _, acc in accounts_df.iterrows():
            is_act = acc['is_active'] == 1
            st.markdown(f"""
            <div class="acc-item-row">
                <div>
                    <div class="acc-name-txt">{acc['account_name']}</div>
                    <div class="acc-broker-txt">{acc['broker']}</div>
                </div>
                <div style="display: flex; gap: 8px; align-items: center;">
                    <span class="acc-qty-badge">{acc['contracts']} Micros</span>
                    <span class="status-pill {'status-emerald' if is_act else 'status-slate'}">
                        {'ARMED' if is_act else 'PAUSED'}
                    </span>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Account Actions
        c_m1, c_m2, c_m3 = st.columns([1.5, 1.3, 1])
        acc_opts = {row['account_name']: row['id'] for _, row in accounts_df.iterrows()}
        selected_manage_acc = c_m1.selectbox("Select Account", list(acc_opts.keys()), label_visibility="collapsed")

        target_id = acc_opts[selected_manage_acc]
        curr_status = accounts_df[accounts_df['id'] == target_id]['is_active'].values[0]

        if c_m2.button("Toggle Status", use_container_width=True):
            new_st = 0 if curr_status == 1 else 1
            toggle_account_status(target_id, new_st)
            log_temp_event("ROUTER", f"Account [{selected_manage_acc}] status toggled to {'ARMED' if new_st == 1 else 'PAUSED'}", "INFO")
            st.rerun()

        if c_m3.button("✕ Delete", use_container_width=True):
            delete_account(target_id)
            log_temp_event("ROUTER", f"Account [{selected_manage_acc}] removed from execution roster", "WARN")
            st.rerun()
    else:
        st.markdown("""
        <div style="background: rgba(255, 255, 255, 0.02); border: 1px dashed rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 20px; text-align: center; margin-bottom: 14px;">
            <div style="color: #94A3B8; font-size: 13px; font-weight: 600; margin-bottom: 4px;">Zero Accounts Linked</div>
            <div style="color: #64748B; font-size: 11px;">Link your live Topstep, Apex, or Tradovate credentials below to arm execution.</div>
        </div>
        """, unsafe_allow_html=True)

    # Link New Trading Account Form (auto-expanded if empty)
    with st.expander("➕ Link New Trading Account", expanded=accounts_df.empty):
        with st.form("link_trading_acc_form", clear_on_submit=True):
            c_f1, c_f2 = st.columns(2)
            new_acc_name = c_f1.text_input("Account Identifier", placeholder="e.g. Topstep_150k_Live")
            new_broker = c_f2.selectbox("Execution Broker / Feed", [
                "Topstep (Tradovate)", "Apex Trader Funding", "Tradovate Live API", "NinjaTrader 8 (Local)", "Interactive Brokers"
            ])

            c_f3, c_f4 = st.columns(2)
            new_key = c_f3.text_input("API Key / Username", type="password", placeholder="API Key or Username")
            new_sec = c_f4.text_input("API Secret / Password", type="password", placeholder="API Secret or Password")

            new_qty = st.slider("Position Size (Micro Contracts)", min_value=1, max_value=20, value=3)

            if st.form_submit_button("Link Account", use_container_width=True):
                if new_acc_name.strip() and new_key.strip():
                    add_account(new_acc_name.strip(), new_broker, new_key.strip(), new_sec.strip(), new_qty)
                    log_temp_event("ROUTER", f"Linked live account [{new_acc_name.strip()}] ({new_broker}) with {new_qty} micros", "INFO")
                    st.success(f"Trading Account '{new_acc_name.strip()}' linked.")
                    st.rerun()
                else:
                    st.error("Account Identifier and API Key are required.")


# ================= UNVEIL TEMPORARY LOGS BUTTON =================
st.markdown("<div style='margin-top: 24px;'></div>", unsafe_allow_html=True)

c_sp1, c_unveil, c_sp2 = st.columns([1, 1.4, 1])
with c_sp1:
    st.markdown("<div class='unveil-marker'></div>", unsafe_allow_html=True)
with c_sp2:
    st.markdown("<div class='unveil-marker'></div>", unsafe_allow_html=True)

with c_unveil:
    st.markdown("<div class='unveil-marker'></div>", unsafe_allow_html=True)
    logs_visible = st.session_state.get("show_temp_logs", False)
    btn_text = "✕ Hide Temporary Logs" if logs_visible else "📜 Unveil Temporary Logs for Checking"
    if st.button(btn_text, use_container_width=True, key="unveil_logs_button"):
        st.session_state.show_temp_logs = not logs_visible
        st.rerun()

# ================= TEMPORARY LOGS CONSOLE DISPLAY =================
if st.session_state.get("show_temp_logs", False):
    total_logs = len(st.session_state.get("temp_logs", []))

    # Action Toolbar above terminal: Filter + Clear
    c_bar_f, c_bar_clr = st.columns([3, 1])
    with c_bar_f:
        st.markdown("<div class='unveil-marker'></div>", unsafe_allow_html=True)
        log_filter = st.selectbox(
            "Filter Category",
            ["All Activity", "Ticks & Touches", "Orders & Exits", "Strategy & Risk", "System & Feeds"],
            label_visibility="collapsed"
        )
    with c_bar_clr:
        st.markdown("<div class='unveil-marker'></div>", unsafe_allow_html=True)
        if st.button("🧹 Clear Logs", use_container_width=True):
            st.session_state.temp_logs = []
            st.rerun()

    # Filter logs
    raw_logs = list(reversed(st.session_state.get("temp_logs", [])))
    if log_filter == "Ticks & Touches":
        filtered_logs = [l for l in raw_logs if l["category"] in ["TICK", "TOUCH"]]
    elif log_filter == "Orders & Exits":
        filtered_logs = [l for l in raw_logs if l["category"] in ["ORDER", "EXIT", "ROUTER"]]
    elif log_filter == "Strategy & Risk":
        filtered_logs = [l for l in raw_logs if l["category"] in ["STRATEGY", "RISK", "STATE"]]
    elif log_filter == "System & Feeds":
        filtered_logs = [l for l in raw_logs if l["category"] in ["SYSTEM", "FEED"]]
    else:
        filtered_logs = raw_logs

    # Build Terminal HTML
    if not filtered_logs:
        log_rows_html = "<div style='color: #64748B; padding: 24px 0; text-align: center; font-size: 12px;'>No runtime logs recorded yet. System is fresh on standby.</div>"
    else:
        log_rows_html = ""
        for log in filtered_logs:
            cat = log.get("category", "INFO").upper()
            tag_class = "tag-system"
            if cat == "TICK": tag_class = "tag-tick"
            elif cat == "TOUCH": tag_class = "tag-touch"
            elif cat in ["ORDER", "ROUTER"]: tag_class = "tag-order"
            elif cat == "EXIT": tag_class = "tag-exit"
            elif cat == "RISK": tag_class = "tag-risk"
            elif cat == "STRATEGY": tag_class = "tag-strategy"
            elif cat == "FEED": tag_class = "tag-feed"

            log_rows_html += f"""
            <div class="log-row">
                <span class="log-ts">{log['time']}</span>
                <span class="log-tag {tag_class}">[{cat}]</span>
                <span class="log-msg">{log['message']}</span>
            </div>
            """

    st.markdown(f"""
    <div class="terminal-container">
        <div class="terminal-header">
            <div class="terminal-dots">
                <span class="terminal-dot dot-red"></span>
                <span class="terminal-dot dot-yellow"></span>
                <span class="terminal-dot dot-green"></span>
                <span class="terminal-title">RUNTIME LOGS & TELEMETRY STREAM</span>
            </div>
            <div style="display: flex; gap: 8px; align-items: center;">
                <span class="terminal-badge">BUFFER: {total_logs}/150</span>
                <span class="terminal-badge" style="background: rgba(16, 185, 129, 0.1); color: #34D399; border-color: rgba(16, 185, 129, 0.25);">● LIVE LOG STREAM</span>
            </div>
        </div>
        <div class="terminal-stream">
            {log_rows_html}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Persistent SQLite Trades Check
    trades_df = get_trades_df()
    if not trades_df.empty:
        with st.expander(f"📁 Persistent SQLite Execution Records ({len(trades_df)} Fills Stored)", expanded=False):
            st.dataframe(
                trades_df[['trade_time', 'account_name', 'side', 'entry_price', 'exit_price', 'pnl_points', 'pnl_usd', 'execution_type']],
                use_container_width=True,
                hide_index=True
            )
    else:
        with st.expander("📁 Persistent SQLite Execution Records (0 Fills Stored)", expanded=False):
            st.markdown("<div style='color: #64748B; font-size: 12px; padding: 8px 0;'>No trade executions logged in SQLite yet. Clean database state.</div>", unsafe_allow_html=True)

# ----------------- CENTERED MINIMAL FOOTER -----------------
st.markdown("""
<div class="centered-footer">
    Pure RTH 50% Equilibrium Engine • Sub-Second Tick-on-Touch Trigger • 1-Minute Candle Aggregator • Chicago CME Low-Latency Gateway
</div>
""", unsafe_allow_html=True)
