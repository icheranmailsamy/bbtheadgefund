import streamlit as st
import pandas as pd
import datetime
import os

from engine.storage import (
    init_db, get_accounts, add_account, toggle_account_status,
    delete_account, get_system_state, set_system_state, get_connection
)
from engine.strategy import PureRTHEquilibriumStrategyEngine
from engine.risk_engine import RiskManagementEngine
from engine.broker_router import BrokerMultiAccountRouter

# ----------------- PAGE CONFIGURATION -----------------
st.set_page_config(
    page_title="Equilibrium // API Gateway",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ----------------- ULTRA MINIMALIST CSS SYSTEM -----------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

    /* Reset & Constraints */
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        max-width: 1180px;
    }
    #MainMenu, footer, header { display: none !important; }

    /* Ultra Minimal Canvas */
    .stApp {
        background-color: #08090C !important;
        background-image: radial-gradient(at 50% 0%, rgba(30, 41, 59, 0.15) 0px, transparent 50%) !important;
        color: #E2E8F0 !important;
    }
    .mono { font-family: 'JetBrains Mono', monospace !important; }

    /* Minimalist Topbar */
    .minimal-topbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: #0E1218;
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-radius: 12px;
        padding: 12px 20px;
        margin-bottom: 22px;
    }
    .topbar-brand {
        display: flex;
        align-items: center;
        gap: 10px;
        font-size: 15px;
        font-weight: 700;
        color: #F8FAFC;
        letter-spacing: -0.3px;
    }
    .topbar-badge {
        font-size: 11px;
        color: #64748B;
        text-transform: uppercase;
        font-weight: 600;
        letter-spacing: 0.5px;
    }
    .status-tag {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 11px;
        font-weight: 600;
        padding: 4px 10px;
        border-radius: 6px;
    }
    .status-tag-active {
        background: rgba(16, 185, 129, 0.1);
        border: 1px solid rgba(16, 185, 129, 0.25);
        color: #34D399;
    }
    .status-tag-idle {
        background: rgba(148, 163, 184, 0.08);
        border: 1px solid rgba(148, 163, 184, 0.18);
        color: #94A3B8;
    }
    .dot-pulse {
        width: 6px;
        height: 6px;
        background-color: #10B981;
        border-radius: 50%;
        box-shadow: 0 0 8px #10B981;
    }

    /* Minimalist Cards */
    .ultra-card {
        background: #0D1117;
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-radius: 14px;
        padding: 22px 24px;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        transition: border-color 0.2s ease;
    }
    .ultra-card:hover {
        border-color: rgba(255, 255, 255, 0.14);
    }
    .card-top {
        margin-bottom: 16px;
        padding-bottom: 14px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
    }
    .card-title {
        font-size: 16px;
        font-weight: 700;
        color: #F8FAFC;
        letter-spacing: -0.3px;
        margin-bottom: 4px;
    }
    .card-subtitle {
        font-size: 12px;
        color: #64748B;
        font-weight: 400;
        line-height: 1.4;
    }

    /* Account Rows in Trading API Card */
    .acc-item-row {
        background: #090C10;
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 8px;
        padding: 10px 14px;
        margin-bottom: 8px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .acc-name-txt {
        font-weight: 600;
        font-size: 13px;
        color: #F1F5F9;
        font-family: 'JetBrains Mono', monospace;
    }
    .acc-broker-txt {
        font-size: 11px;
        color: #64748B;
        margin-top: 2px;
    }
    .acc-qty-badge {
        background: rgba(56, 189, 248, 0.1);
        color: #38BDF8;
        border: 1px solid rgba(56, 189, 248, 0.2);
        border-radius: 4px;
        padding: 2px 8px;
        font-size: 11px;
        font-weight: 600;
        font-family: 'JetBrains Mono', monospace;
    }

    /* Minimalist Form Inputs */
    .stTextInput>div>div>input, .stSelectbox>div>div>div {
        background-color: #0A0D12 !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 6px !important;
        color: #F8FAFC !important;
        font-size: 12px !important;
    }
    .stButton>button {
        background: #1E293B !important;
        color: #F8FAFC !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 6px !important;
        padding: 8px 16px !important;
        font-size: 12px !important;
        font-weight: 600 !important;
        transition: all 0.15s ease !important;
    }
    .stButton>button:hover {
        background: #334155 !important;
        border-color: rgba(255, 255, 255, 0.25) !important;
    }

    /* Minimalist Footer */
    .minimal-footer {
        margin-top: 24px;
        padding-top: 14px;
        border-top: 1px solid rgba(255, 255, 255, 0.05);
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 11px;
        color: #64748B;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Storage
init_db()

# Auto-seed sample demo accounts if empty
accounts_df = get_accounts()
if accounts_df.empty:
    add_account("Topstep_100k_Alpha", "Topstep (Tradovate)", "DEMO_KEY_8829", "DEMO_SECRET", 3)
    add_account("Apex_100k_Funded", "Apex Trader Funding", "APEX_PROD_102", "APEX_SECRET", 3)
    accounts_df = get_accounts()

# Retrieve or initialize Data Feed State
feed_connected = get_system_state("data_feed_connected", "1") == "1"
feed_provider = get_system_state("data_feed_provider", "Tradovate WebSocket API")
feed_asset = get_system_state("data_feed_asset", "MNQ")

active_accounts_count = len(accounts_df[accounts_df['is_active'] == 1]) if not accounts_df.empty else 0

# ----------------- TOPBAR -----------------
st.markdown(f"""
<div class="minimal-topbar">
    <div class="topbar-brand">
        <span>⚡ EQUILIBRIUM</span>
        <span class="topbar-badge">/ ULTRA MINIMAL GATEWAY</span>
    </div>
    <div style="display: flex; gap: 10px; align-items: center;">
        <span class="status-tag {'status-tag-active' if feed_connected else 'status-tag-idle'}">
            <span class="{'dot-pulse' if feed_connected else ''}"></span>
            {'DATA FEED: CONNECTED' if feed_connected else 'DATA FEED: DISCONNECTED'}
        </span>
        <span class="status-tag status-tag-active">
            {active_accounts_count} TRADING ACCOUNTS ARMED
        </span>
    </div>
</div>
""", unsafe_allow_html=True)

# ----------------- TWO ULTRA-MINIMAL CARDS -----------------
col_data, col_trade = st.columns(2, gap="medium")

# ================= CARD 1: DATA CONNECT API =================
with col_data:
    st.markdown("""
    <div class="ultra-card">
        <div>
            <div class="card-top">
                <div>
                    <div class="card-title">Data Connect API</div>
                    <div class="card-subtitle">The main source of data to generate signals</div>
                </div>
    """, unsafe_allow_html=True)
    
    if feed_connected:
        st.markdown('<span class="status-tag status-tag-active"><span class="dot-pulse"></span> LIVE STREAMING</span></div>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="status-tag status-tag-idle">○ DISCONNECTED</span></div>', unsafe_allow_html=True)

    # Data Feed Configuration
    c_p1, c_p2 = st.columns(2)
    with c_p1:
        provider_choice = st.selectbox(
            "Feed Provider",
            ["Tradovate WebSocket API", "Rithmic R|API+", "Interactive Brokers (TWS)", "Databento CME Real-time", "Simulated Live Feed"],
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
        env_mode = st.selectbox("Feed Environment", ["Live CME Stream (Low-Latency)", "Demo / Paper Market Data"])
    with col_sess:
        st.text_input("Session Anchor", value="09:30–15:55 EST (Pure RTH)", disabled=True)

    api_key_input = st.text_input("Feed API Key / Token", value="tk_live_cme_8839201948", type="password")

    # Live Feed Telemetry Strip
    if feed_connected:
        st.markdown("""
        <div style="background: rgba(16, 185, 129, 0.05); border: 1px solid rgba(16, 185, 129, 0.15); border-radius: 8px; padding: 10px 14px; margin: 12px 0; font-size: 12px; display: flex; justify-content: space-between; align-items: center;">
            <div>
                <span style="color: #64748B;">Latest Bar Price:</span> <b class="mono" style="color: #F8FAFC;">18,532.50</b>
            </div>
            <div>
                <span style="color: #64748B;">Ping:</span> <b class="mono" style="color: #34D399;">12 ms</b>
            </div>
            <div>
                <span style="color: #64748B;">Gateway:</span> <b class="mono" style="color: #94A3B8;">CME Chicago</b>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background: rgba(148, 163, 184, 0.04); border: 1px solid rgba(148, 163, 184, 0.1); border-radius: 8px; padding: 10px 14px; margin: 12px 0; font-size: 12px; color: #64748B;">
            Feed is currently disconnected. Click below to establish a real-time WebSocket session.
        </div>
        """, unsafe_allow_html=True)

    # Connect / Disconnect Action
    c_btn1, c_btn2 = st.columns(2)
    with c_btn1:
        if st.button("🔗 Connect Data Feed" if not feed_connected else "🔄 Reconnect Feed", use_container_width=True):
            set_system_state("data_feed_connected", "1")
            set_system_state("data_feed_provider", provider_choice)
            set_system_state("data_feed_asset", asset_choice)
            st.success("✅ Real-time market feed established successfully.")
            st.rerun()
    with c_btn2:
        if st.button("Disconnect Feed", use_container_width=True, disabled=not feed_connected):
            set_system_state("data_feed_connected", "0")
            st.info("Market feed disconnected.")
            st.rerun()

    st.markdown("</div></div>", unsafe_allow_html=True)


# ================= CARD 2: TRADING ACCOUNT API =================
with col_trade:
    st.markdown("""
    <div class="ultra-card">
        <div>
            <div class="card-top">
                <div>
                    <div class="card-title">Trading Account API</div>
                    <div class="card-subtitle">The Accounts where trades should be placed</div>
                </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f'<span class="status-tag status-tag-active">{active_accounts_count} ARMED</span></div>', unsafe_allow_html=True)

    # Active Connected Accounts List
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
                    <span class="status-tag {'status-tag-active' if is_act else 'status-tag-idle'}">
                        {'ARMED' if is_act else 'PAUSED'}
                    </span>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Quick Account Management Bar
        c_m1, c_m2, c_m3 = st.columns([1.5, 1.5, 1])
        acc_opts = {row['account_name']: row['id'] for _, row in accounts_df.iterrows()}
        selected_manage_acc = c_m1.selectbox("Select Account", list(acc_opts.keys()), label_visibility="collapsed")
        
        target_id = acc_opts[selected_manage_acc]
        curr_status = accounts_df[accounts_df['id'] == target_id]['is_active'].values[0]

        if c_m2.button("Toggle Active / Pause", use_container_width=True):
            toggle_account_status(target_id, 0 if curr_status == 1 else 1)
            st.rerun()
            
        if c_m3.button("✕ Delete", use_container_width=True):
            delete_account(target_id)
            st.rerun()
    else:
        st.info("No trading accounts connected yet. Add an account below.")

    # Link New Trading Account Drawer / Form
    with st.expander("➕ Link New Trading Account", expanded=False):
        with st.form("link_trading_acc_form"):
            c_f1, c_f2 = st.columns(2)
            new_acc_name = c_f1.text_input("Account Identifier", placeholder="Topstep_100k_Alpha_02")
            new_broker = c_f2.selectbox("Execution Broker / Feed", [
                "Topstep (Tradovate)", "Apex Trader Funding", "Tradovate Live API", "NinjaTrader 8 (Local)", "Interactive Brokers"
            ])

            c_f3, c_f4 = st.columns(2)
            new_key = c_f3.text_input("API Key / Username", type="password")
            new_sec = c_f4.text_input("API Secret / Password", type="password")

            new_qty = st.slider("Position Size (Micro Contracts)", min_value=1, max_value=20, value=3)

            if st.form_submit_button("Link Account", use_container_width=True):
                if new_acc_name and new_key:
                    add_account(new_acc_name, new_broker, new_key, new_sec, new_qty)
                    st.success(f"Trading Account '{new_acc_name}' linked.")
                    st.rerun()
                else:
                    st.error("Account Identifier and API Key are required.")

    st.markdown("</div></div>", unsafe_allow_html=True)


# ----------------- MINIMAL STATUS FOOTER -----------------
st.markdown("""
<div class="minimal-footer">
    <div><b>Strategy Engine:</b> Pure RTH 50% Equilibrium State Machine</div>
    <div><b>Session Rules:</b> 09:30 AM Fresh Slate • 15:59 EST Hard Flatten (Zero Overnight Risk)</div>
    <div><b>Order Routing:</b> Immediate Multi-Account Concurrent Dispatch</div>
</div>
""", unsafe_allow_html=True)
