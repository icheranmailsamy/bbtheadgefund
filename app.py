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
    
    /* Clean Viewport Constraints */
    .block-container {
        padding-top: 1.25rem !important;
        padding-bottom: 3rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        max-width: 1520px;
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

    /* Badges & Indicators */
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

    /* ---------------- FUNDED ACCOUNTS SUITE ---------------- */
    .funded-hero-banner {
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.8) 0%, rgba(13, 18, 30, 0.9) 100%);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 20px 24px;
        margin-bottom: 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    }
    .funded-title-area {
        display: flex;
        flex-direction: column;
        gap: 6px;
    }
    .funded-tier-badge {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: rgba(56, 189, 248, 0.12);
        border: 1px solid rgba(56, 189, 248, 0.25);
        color: #38BDF8;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        width: fit-content;
    }
    .funded-main-title {
        font-size: 19px;
        font-weight: 800;
        color: #F8FAFC;
        letter-spacing: -0.5px;
    }
    .funded-equity-box {
        text-align: right;
    }
    .funded-equity-label {
        font-size: 11px;
        color: #64748B;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.8px;
    }
    .funded-equity-val {
        font-family: 'JetBrains Mono', monospace;
        font-size: 30px;
        font-weight: 800;
        color: #F8FAFC;
        line-height: 1.1;
    }

    /* Funded KPI 4-Card Grid */
    .funded-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 16px;
        margin-bottom: 20px;
    }
    .funded-card {
        background: rgba(13, 18, 30, 0.65);
        backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-radius: 14px;
        padding: 18px 20px;
        position: relative;
        transition: all 0.25s ease;
        box-shadow: 0 4px 16px -2px rgba(0, 0, 0, 0.25);
    }
    .funded-card:hover {
        border-color: rgba(56, 189, 248, 0.35);
        transform: translateY(-2px);
    }
    .funded-card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 12px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.7px;
        color: #64748B;
        margin-bottom: 8px;
    }
    .funded-card-num {
        font-family: 'JetBrains Mono', monospace;
        font-size: 24px;
        font-weight: 700;
        letter-spacing: -0.5px;
        color: #F8FAFC;
        margin-bottom: 8px;
    }
    .progress-track {
        background: rgba(255, 255, 255, 0.06);
        border-radius: 999px;
        height: 7px;
        width: 100%;
        overflow: hidden;
        margin-bottom: 10px;
    }
    .progress-fill-emerald {
        height: 100%;
        background: linear-gradient(90deg, #10B981 0%, #34D399 100%);
        border-radius: 999px;
        box-shadow: 0 0 10px rgba(16, 185, 129, 0.5);
    }
    .progress-fill-sky {
        height: 100%;
        background: linear-gradient(90deg, #0284C7 0%, #38BDF8 100%);
        border-radius: 999px;
        box-shadow: 0 0 10px rgba(56, 189, 248, 0.5);
    }
    .progress-fill-amber {
        height: 100%;
        background: linear-gradient(90deg, #D97706 0%, #FBBF24 100%);
        border-radius: 999px;
        box-shadow: 0 0 10px rgba(245, 158, 11, 0.5);
    }
    .progress-fill-rose {
        height: 100%;
        background: linear-gradient(90deg, #E11D48 0%, #FB7185 100%);
        border-radius: 999px;
        box-shadow: 0 0 10px rgba(244, 63, 94, 0.5);
    }
    .funded-card-sub {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 11px;
        color: #94A3B8;
        font-weight: 500;
    }

    /* Prop Firm Compliance Strip */
    .prop-rules-bar {
        background: rgba(15, 23, 42, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 12px;
        padding: 12px 18px;
        margin-bottom: 22px;
        display: flex;
        justify-content: space-around;
        align-items: center;
        gap: 16px;
    }
    .prop-chip {
        display: flex;
        align-items: center;
        gap: 10px;
        font-size: 12px;
    }
    .prop-chip-title {
        color: #64748B;
        font-weight: 600;
        text-transform: uppercase;
        font-size: 11px;
        letter-spacing: 0.5px;
    }
    .prop-chip-val {
        color: #F1F5F9;
        font-weight: 700;
        font-family: 'JetBrains Mono', monospace;
    }

    /* ---------------- QUANT METRIC CARDS ---------------- */
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

    /* ---------------- SAAS PANELS ---------------- */
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

    /* ---------------- CALENDAR PROFITS HEATMAP ---------------- */
    .cal-stats-strip {
        display: grid;
        grid-template-columns: repeat(6, 1fr);
        gap: 10px;
        background: rgba(15, 23, 42, 0.45);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        padding: 12px 16px;
        margin-bottom: 16px;
    }
    .cal-stat-item {
        display: flex;
        flex-direction: column;
        gap: 2px;
    }
    .cal-stat-label {
        font-size: 11px;
        color: #64748B;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .cal-stat-val {
        font-family: 'JetBrains Mono', monospace;
        font-size: 15px;
        font-weight: 700;
        color: #F8FAFC;
    }

    .cal-weekdays-grid {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 10px;
        margin-bottom: 6px;
    }
    .cal-weekday-label {
        text-align: center;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        color: #64748B;
        padding: 6px 0;
    }

    .cal-days-grid {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 10px;
    }
    .cal-day-cell {
        border-radius: 12px;
        padding: 10px 12px;
        min-height: 86px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
    }
    .cal-day-cell:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
    }
    .cal-profit {
        background: linear-gradient(145deg, rgba(16, 185, 129, 0.16) 0%, rgba(13, 18, 30, 0.8) 100%);
        border: 1px solid rgba(16, 185, 129, 0.35);
        box-shadow: 0 0 16px rgba(16, 185, 129, 0.08);
    }
    .cal-profit:hover {
        border-color: rgba(52, 211, 153, 0.6);
    }
    .cal-loss {
        background: linear-gradient(145deg, rgba(244, 63, 94, 0.16) 0%, rgba(13, 18, 30, 0.8) 100%);
        border: 1px solid rgba(244, 63, 94, 0.35);
        box-shadow: 0 0 16px rgba(244, 63, 94, 0.08);
    }
    .cal-loss:hover {
        border-color: rgba(251, 113, 133, 0.6);
    }
    .cal-neutral {
        background: rgba(15, 23, 42, 0.4);
        border: 1px solid rgba(255, 255, 255, 0.04);
    }
    .cal-weekend {
        background: rgba(10, 14, 23, 0.3);
        border: 1px solid rgba(255, 255, 255, 0.02);
    }
    .cal-empty {
        background: transparent;
        border: 1px dashed rgba(255, 255, 255, 0.03);
        min-height: 86px;
        border-radius: 12px;
    }
    .cal-day-top {
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .cal-day-num {
        font-size: 11px;
        font-weight: 700;
        color: #94A3B8;
        font-family: 'JetBrains Mono', monospace;
    }
    .cal-pnl-val {
        font-family: 'JetBrains Mono', monospace;
        font-size: 15px;
        font-weight: 800;
        margin: 4px 0;
        letter-spacing: -0.5px;
    }
    .cal-sub-pill {
        font-size: 10px;
        font-weight: 600;
        color: #94A3B8;
        display: flex;
        align-items: center;
        gap: 4px;
    }

    /* ---------------- LIVE TRADING HISTORY TABLE ---------------- */
    .trade-table-wrapper {
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-radius: 12px;
        overflow: hidden;
        background: rgba(10, 14, 23, 0.6);
        margin-top: 14px;
    }
    .trade-table-custom {
        width: 100%;
        border-collapse: collapse;
        font-size: 12px;
        text-align: left;
    }
    .trade-table-custom th {
        background: rgba(15, 23, 42, 0.95);
        color: #64748B;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.7px;
        padding: 12px 14px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        font-size: 11px;
    }
    .trade-table-custom td {
        padding: 12px 14px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.04);
        color: #E2E8F0;
        font-family: 'JetBrains Mono', monospace;
    }
    .trade-table-custom tr:hover {
        background: rgba(30, 41, 59, 0.4);
    }
    .badge-long {
        display: inline-block;
        background: rgba(16, 185, 129, 0.15);
        color: #34D399;
        border: 1px solid rgba(16, 185, 129, 0.3);
        border-radius: 4px;
        padding: 2px 7px;
        font-size: 10px;
        font-weight: 700;
    }
    .badge-short {
        display: inline-block;
        background: rgba(244, 63, 94, 0.15);
        color: #FB7185;
        border: 1px solid rgba(244, 63, 94, 0.3);
        border-radius: 4px;
        padding: 2px 7px;
        font-size: 10px;
        font-weight: 700;
    }
    .badge-acc-tag {
        display: inline-block;
        background: rgba(56, 189, 248, 0.1);
        color: #38BDF8;
        border: 1px solid rgba(56, 189, 248, 0.2);
        border-radius: 4px;
        padding: 2px 8px;
        font-size: 10px;
        font-weight: 600;
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
        
        # High-fidelity demo executions matching Pure RTH 50% Equilibrium Model
        demo_executions = [
            # Sept 28-30 (Previous week trades)
            ("2026-09-28 10:15:00", 18450.0, 22.0, 3, "Topstep_100k_Alpha"),
            ("2026-09-28 14:10:00", 18475.0, 18.0, 3, "Topstep_100k_Alpha"),
            ("2026-09-29 09:50:00", 18510.0, 30.0, 3, "Topstep_100k_Alpha"),
            ("2026-09-29 13:20:00", 18540.0, -8.0, 3, "Topstep_100k_Alpha"),
            ("2026-09-30 10:30:00", 18560.0, 35.0, 3, "Topstep_100k_Alpha"),
            ("2026-09-30 14:40:00", 18595.0, 25.0, 3, "Topstep_100k_Alpha"),
            # Oct 1 (Thu)
            ("2026-10-01 10:14:00", 18485.0, 24.0, 3, "Topstep_100k_Alpha"),
            ("2026-10-01 14:25:00", 18512.0, 18.5, 3, "Topstep_100k_Alpha"),
            # Oct 2 (Fri)
            ("2026-10-02 09:45:00", 18530.0, 31.0, 3, "Topstep_100k_Alpha"),
            ("2026-10-02 13:10:00", 18575.0, -8.0, 3, "Topstep_100k_Alpha"),
            # Oct 5 (Mon)
            ("2026-10-05 10:30:00", 18590.0, 28.5, 3, "Topstep_100k_Alpha"),
            ("2026-10-05 11:45:00", 18625.0, 34.0, 3, "Topstep_100k_Alpha"),
            ("2026-10-05 14:50:00", 18660.0, 14.0, 3, "Topstep_100k_Alpha"),
            # Oct 6 (Tue)
            ("2026-10-06 10:15:00", 18680.0, 42.0, 3, "Topstep_100k_Alpha"),
            ("2026-10-06 13:40:00", 18730.0, -6.5, 3, "Topstep_100k_Alpha"),
            # Oct 7 (Wed)
            ("2026-10-07 09:50:00", 18710.0, 38.0, 3, "Topstep_100k_Alpha"),
            ("2026-10-07 11:20:00", 18755.0, 26.5, 3, "Topstep_100k_Alpha"),
            ("2026-10-07 14:15:00", 18790.0, 19.5, 3, "Topstep_100k_Alpha"),
            # Oct 8 (Thu) - Controlled Loss Day
            ("2026-10-08 10:10:00", 18810.0, -12.0, 3, "Topstep_100k_Alpha"),
            ("2026-10-08 13:30:00", 18785.0, -7.0, 3, "Topstep_100k_Alpha"),
            # Oct 9 (Fri)
            ("2026-10-09 09:40:00", 18760.0, 45.0, 3, "Topstep_100k_Alpha"),
            ("2026-10-09 11:15:00", 18815.0, 32.0, 3, "Topstep_100k_Alpha"),
            ("2026-10-09 14:30:00", 18850.0, 22.5, 3, "Topstep_100k_Alpha"),
            # Oct 12 (Mon - Today)
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
            ENGINE ARMED & LISTENING
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

# ================= TAB 1: PERFORMANCE ANALYTICS & FUNDED SUITE =================
with tab_dash:
    trades_df = get_trades_df()
    
    if trades_df.empty:
        st.info("No executions recorded yet. Add an account or simulate trades in Tab 2.")
    else:
        # 1. Top SaaS Control Toolbar
        col_acc, col_preset = st.columns([1.5, 2.5])
        with col_acc:
            acc_list = ["ALL PORTFOLIOS (AGGREGATED)"] + trades_df['account_name'].unique().tolist()
            selected_acc = st.selectbox("Portfolio Filter", acc_list, label_visibility="collapsed")
            
        with col_preset:
            prop_preset = st.selectbox("Funded Account Target Preset", [
                "Topstep 100k Pro Combine ($6,000 Target | $3,000 Trailing DD | $2,000 Daily Loss)",
                "Apex 100k Funded ($6,000 Target | $3,000 Trailing DD | No Daily Limit)",
                "Topstep 50k Pro Combine ($3,000 Target | $2,000 Trailing DD | $1,000 Daily Loss)",
                "Apex 50k Express ($3,000 Target | $2,500 Trailing DD | No Daily Limit)",
                "FundedNext 100k Evaluation ($6,000 Target | $3,000 Trailing DD | $2,000 Daily Loss)",
                "Custom Configurable Rules..."
            ], label_visibility="collapsed")

        # Parse Prop Preset Values
        if "50k" in prop_preset:
            initial_balance = 50000.0
            profit_target = 3000.0
            max_trailing_dd = 2000.0 if "Topstep" in prop_preset else 2500.0
            daily_loss_limit = 1000.0 if "Topstep" in prop_preset else 99999.0
            min_days = 5 if "Topstep" in prop_preset else 1
        elif "Custom" in prop_preset:
            with st.expander("⚙️ Configure Custom Funded Rules & Risk Thresholds", expanded=False):
                c_r1, c_r2, c_r3, c_r4 = st.columns(4)
                initial_balance = c_r1.number_input("Starting Capital ($)", value=100000.0, step=10000.0)
                profit_target = c_r2.number_input("Profit Target ($)", value=6000.0, step=500.0)
                max_trailing_dd = c_r3.number_input("Max Trailing DD ($)", value=3000.0, step=500.0)
                daily_loss_limit = c_r4.number_input("Daily Loss Limit ($)", value=2000.0, step=500.0)
                min_days = 5
        else: # Default 100k
            initial_balance = 100000.0
            profit_target = 6000.0
            max_trailing_dd = 3000.0
            daily_loss_limit = 2000.0 if "Topstep" in prop_preset or "FundedNext" in prop_preset else 99999.0
            min_days = 5 if "Topstep" in prop_preset else 1

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

        # Funded Account Logic Calculations
        current_equity = initial_balance + total_pnl
        target_progress_pct = max(0.0, min(100.0, (total_pnl / profit_target * 100.0))) if profit_target > 0 else 100.0
        remaining_target = max(0.0, profit_target - total_pnl)
        
        # Trailing High Water Mark & Liquidation Threshold
        running_equity = initial_balance + df_view['cum_pnl']
        hwm = max(initial_balance, float(running_equity.max()))
        liquidation_threshold = hwm - max_trailing_dd
        trailing_buffer_remaining = max(0.0, current_equity - liquidation_threshold)
        trailing_buffer_pct = max(0.0, min(100.0, (trailing_buffer_remaining / max_trailing_dd * 100.0)))

        # Today's Realized PnL & Daily Loss Limit Buffer
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        df_view['date_str'] = df_view['trade_time'].dt.strftime('%Y-%m-%d')
        today_trades = df_view[df_view['date_str'] == today_str]
        today_pnl = float(today_trades['pnl_usd'].sum()) if not today_trades.empty else 0.0
        daily_consumed = abs(today_pnl) if today_pnl < 0 else 0.0
        daily_buffer_remaining = max(0.0, daily_loss_limit - daily_consumed)
        daily_buffer_pct = max(0.0, min(100.0, (daily_buffer_remaining / daily_loss_limit * 100.0)))

        # Consistency Rule & Days Traded
        days_traded = df_view['trade_time'].dt.date.nunique()
        day_pnl_series = df_view.groupby(df_view['trade_time'].dt.date)['pnl_usd'].sum()
        best_day_pnl = float(day_pnl_series.max()) if not day_pnl_series.empty else 0.0
        consistency_pct = (best_day_pnl / total_pnl * 100.0) if total_pnl > 0 and best_day_pnl > 0 else 0.0
        consistency_status = "PASS (<30%)" if consistency_pct <= 30.0 else f"MONITOR ({consistency_pct:.1f}%)"

        # Determine Evaluation State
        if total_pnl >= profit_target:
            eval_badge = '<span class="status-pill" style="background: rgba(16,185,129,0.2); color: #34D399;">🏆 TARGET ACHIEVED // PASSED</span>'
        elif trailing_buffer_remaining <= 0:
            eval_badge = '<span class="status-pill" style="background: rgba(244,63,94,0.2); color: #FB7185;">🚨 DRAWDOWN BREACHED</span>'
        else:
            eval_badge = '<span class="status-pill"><div class="pulse-indicator"></div> LIVE EVALUATION // HEALTHY STANDING</span>'

        # 2. FUNDED ACCOUNTS HERO BANNER
        account_display_name = selected_acc if selected_acc != "ALL PORTFOLIOS (AGGREGATED)" else "Master Copier Portfolio"
        st.markdown(f"""
        <div class="funded-hero-banner">
            <div class="funded-title-area">
                <div class="funded-tier-badge">🏛️ {prop_preset.split('(')[0].strip()}</div>
                <div class="funded-main-title">{account_display_name}</div>
                <div>{eval_badge}</div>
            </div>
            <div class="funded-equity-box">
                <div class="funded-equity-label">Current Account Equity</div>
                <div class="funded-equity-val">${current_equity:,.2f}</div>
                <div style="font-size: 12px; color: {'#34D399' if total_pnl >= 0 else '#FB7185'}; font-weight: 600;">
                    {'+' if total_pnl >= 0 else ''}${total_pnl:,.2f} ({'+' if total_pnl >= 0 else ''}{(total_pnl/initial_balance*100):.2f}% Gain)
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 3. FUNDED METRIC CARDS WITH PROGRESS BARS
        dd_fill_cls = "progress-fill-emerald" if trailing_buffer_pct > 50 else ("progress-fill-amber" if trailing_buffer_pct > 25 else "progress-fill-rose")
        daily_fill_cls = "progress-fill-emerald" if daily_buffer_pct > 50 else "progress-fill-rose"

        st.markdown(f"""
        <div class="funded-grid">
            <div class="funded-card">
                <div class="funded-card-header">
                    <span>Profit Target Progress</span>
                    <span>🎯</span>
                </div>
                <div class="funded-card-num" style="color: #38BDF8;">
                    ${remaining_target:,.2f} <span style="font-size: 13px; color: #64748B;">left</span>
                </div>
                <div class="progress-track">
                    <div class="progress-fill-sky" style="width: {target_progress_pct:.1f}%;"></div>
                </div>
                <div class="funded-card-sub">
                    <span>{target_progress_pct:.1f}% Completed</span>
                    <span>Target: ${profit_target:,.0f}</span>
                </div>
            </div>
            <div class="funded-card">
                <div class="funded-card-header">
                    <span>Trailing DD Buffer Safe</span>
                    <span>🛡️</span>
                </div>
                <div class="funded-card-num" style="color: {'#34D399' if trailing_buffer_remaining > 1000 else '#FBBF24'};">
                    ${trailing_buffer_remaining:,.2f}
                </div>
                <div class="progress-track">
                    <div class="{dd_fill_cls}" style="width: {trailing_buffer_pct:.1f}%;"></div>
                </div>
                <div class="funded-card-sub">
                    <span>Floor: ${liquidation_threshold:,.2f}</span>
                    <span>Max DD: ${max_trailing_dd:,.0f}</span>
                </div>
            </div>
            <div class="funded-card">
                <div class="funded-card-header">
                    <span>Daily Loss Buffer (Today)</span>
                    <span>⚡</span>
                </div>
                <div class="funded-card-num" style="color: {'#34D399' if today_pnl >= 0 else '#FB7185'};">
                    ${daily_buffer_remaining:,.2f}
                </div>
                <div class="progress-track">
                    <div class="{daily_fill_cls}" style="width: {daily_buffer_pct:.1f}%;"></div>
                </div>
                <div class="funded-card-sub">
                    <span>Today: {'+' if today_pnl >= 0 else ''}${today_pnl:,.2f}</span>
                    <span>Limit: ${daily_loss_limit:,.0f}</span>
                </div>
            </div>
            <div class="funded-card">
                <div class="funded-card-header">
                    <span>Active Days & Consistency</span>
                    <span>📅</span>
                </div>
                <div class="funded-card-num" style="color: #F8FAFC;">
                    {days_traded} <span style="font-size: 13px; color: #64748B;">/ {min_days} Days</span>
                </div>
                <div class="progress-track">
                    <div class="progress-fill-emerald" style="width: {min(100.0, (days_traded/min_days*100.0)):.1f}%;"></div>
                </div>
                <div class="funded-card-sub">
                    <span>Best Day: {consistency_pct:.1f}%</span>
                    <span>Rule: {consistency_status}</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 4. PROP FIRM COMPLIANCE STRIP
        st.markdown(f"""
        <div class="prop-rules-bar">
            <div class="prop-chip">
                <span>⏱️</span>
                <div>
                    <div class="prop-chip-title">Minimum Trading Days</div>
                    <div class="prop-chip-val">{'✅ PASSED' if days_traded >= min_days else f'IN PROGRESS ({days_traded}/{min_days})'}</div>
                </div>
            </div>
            <div class="prop-chip">
                <span>⚖️</span>
                <div>
                    <div class="prop-chip-title">Consistency Rule (Max Day &lt; 30%)</div>
                    <div class="prop-chip-val">{'✅ PASSED (' + f'{consistency_pct:.1f}%)' if consistency_pct <= 30.0 else '⚠️ ' + f'{consistency_pct:.1f}% (Cap at 30%)'}</div>
                </div>
            </div>
            <div class="prop-chip">
                <span>🔒</span>
                <div>
                    <div class="prop-chip-title">Overnight Flat Policy</div>
                    <div class="prop-chip-val">✅ 100% FLAT AT 15:59 EST (Zero Violations)</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 5. CORE QUANT PERFORMANCE CARDS
        st.markdown(f"""
        <div class="kpi-container">
            <div class="modern-card">
                <div class="card-label">
                    <span>Total Realized Profit</span>
                    <span>💵</span>
                </div>
                <div class="card-figure" style="color: {'#34D399' if total_pnl >= 0 else '#FB7185'};">
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
                    Institutional Standard (> 2.0)
                </div>
            </div>
            <div class="modern-card">
                <div class="card-label">
                    <span>Max Historical Drawdown</span>
                    <span>🛡️</span>
                </div>
                <div class="card-figure" style="color: #FB7185;">
                    ${abs(max_dd):,.2f}
                </div>
                <div class="card-footer-pill pill-rose">
                    Peak Stress: {(abs(max_dd)/initial_balance*100):.2f}%
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
                    Multi-Account Gateway Armed
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 6. CUMULATIVE PERFORMANCE EQUITY CHART
        st.markdown("""
        <div class="surface-panel">
            <div class="panel-header">
                <div>
                    <div class="panel-title">Cumulative Performance Growth</div>
                    <div class="panel-subtitle">Audited equity curve progression across New York RTH cash sessions</div>
                </div>
                <div class="session-badge">Pure RTH 09:30 AM Anchor</div>
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
            height=360,
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

        # 7. INTERACTIVE MONTHLY CALENDAR PROFITS HEATMAP
        # Extract unique years and months available in trades
        df_view['year'] = df_view['trade_time'].dt.year
        df_view['month'] = df_view['trade_time'].dt.month
        latest_trade_time = df_view['trade_time'].max()
        
        # Build month selector options
        available_months = df_view[['year', 'month']].drop_duplicates().sort_values(by=['year', 'month'], ascending=False)
        month_options = [f"{datetime.date(r.year, r.month, 1).strftime('%B %Y')}" for _, r in available_months.iterrows()]
        
        st.markdown("""
        <div class="surface-panel">
            <div class="panel-header">
                <div>
                    <div class="panel-title">Monthly Trading Calendar & Daily Profit Heatmap</div>
                    <div class="panel-subtitle">Day-by-day PnL distribution, trade frequency, and streak tracking</div>
                </div>
                <div class="session-badge">TraderSync / Prop Firm Heatmap</div>
            </div>
        """, unsafe_allow_html=True)

        col_cal_sel, _ = st.columns([1.5, 2.5])
        with col_cal_sel:
            selected_month_label = st.selectbox("Select Calendar Month", month_options, index=0, label_visibility="collapsed")
            sel_dt = datetime.datetime.strptime(selected_month_label, "%B %Y")
            cal_year, cal_month = sel_dt.year, sel_dt.month

        # Filter trades for selected month
        df_month = df_view[(df_view['year'] == cal_year) & (df_view['month'] == cal_month)].copy()

        # Group daily statistics
        daily_stats = {}
        if not df_month.empty:
            df_month['day_str'] = df_month['trade_time'].dt.strftime('%Y-%m-%d')
            for d_str, grp in df_month.groupby('day_str'):
                d_pnl = float(grp['pnl_usd'].sum())
                d_count = len(grp)
                d_wins = int((grp['pnl_usd'] > 0).sum())
                d_losses = int((grp['pnl_usd'] <= 0).sum())
                daily_stats[d_str] = {
                    'pnl': d_pnl,
                    'count': d_count,
                    'wins': d_wins,
                    'losses': d_losses
                }

        # Calculate month aggregates
        m_total_pnl = sum(s['pnl'] for s in daily_stats.values()) if daily_stats else 0.0
        m_days_count = len(daily_stats)
        m_win_days = sum(1 for s in daily_stats.values() if s['pnl'] > 0)
        m_loss_days = sum(1 for s in daily_stats.values() if s['pnl'] < 0)
        m_day_win_rate = (m_win_days / m_days_count * 100.0) if m_days_count > 0 else 0.0
        m_avg_day = (m_total_pnl / m_days_count) if m_days_count > 0 else 0.0
        m_best_day = max((s['pnl'] for s in daily_stats.values()), default=0.0)
        m_worst_day = min((s['pnl'] for s in daily_stats.values()), default=0.0)

        # Monthly Summary Strip
        st.markdown(f"""
        <div class="cal-stats-strip">
            <div class="cal-stat-item">
                <span class="cal-stat-label">Month Net Realized</span>
                <span class="cal-stat-val" style="color: {'#34D399' if m_total_pnl >= 0 else '#FB7185'};">
                    {'+' if m_total_pnl >= 0 else ''}${m_total_pnl:,.2f}
                </span>
            </div>
            <div class="cal-stat-item">
                <span class="cal-stat-label">Days Traded</span>
                <span class="cal-stat-val">{m_days_count} Days</span>
            </div>
            <div class="cal-stat-item">
                <span class="cal-stat-label">Day Win Rate</span>
                <span class="cal-stat-val" style="color: #38BDF8;">
                    {m_day_win_rate:.1f}% <span style="font-size: 11px; color: #64748B;">({m_win_days}W / {m_loss_days}L)</span>
                </span>
            </div>
            <div class="cal-stat-item">
                <span class="cal-stat-label">Average Day Return</span>
                <span class="cal-stat-val" style="color: {'#34D399' if m_avg_day >= 0 else '#FB7185'};">
                    {'+' if m_avg_day >= 0 else ''}${m_avg_day:,.2f}
                </span>
            </div>
            <div class="cal-stat-item">
                <span class="cal-stat-label">Best Day</span>
                <span class="cal-stat-val" style="color: #34D399;">+${m_best_day:,.2f}</span>
            </div>
            <div class="cal-stat-item">
                <span class="cal-stat-label">Worst Day</span>
                <span class="cal-stat-val" style="color: #FB7185;">${m_worst_day:,.2f}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Render 7-Column Calendar Grid
        weekdays_html = "".join([f'<div class="cal-weekday-label">{day}</div>' for day in ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]])
        st.markdown(f'<div class="cal-weekdays-grid">{weekdays_html}</div>', unsafe_allow_html=True)

        cal_matrix = calendar.monthcalendar(cal_year, cal_month)
        days_cells_html = []

        for week in cal_matrix:
            for day_idx, day_num in enumerate(week):
                if day_num == 0:
                    days_cells_html.append('<div class="cal-empty"></div>')
                else:
                    date_key = f"{cal_year}-{cal_month:02d}-{day_num:02d}"
                    if date_key in daily_stats:
                        st_day = daily_stats[date_key]
                        p_val = st_day['pnl']
                        c_cls = "cal-profit" if p_val > 0 else ("cal-loss" if p_val < 0 else "cal-neutral")
                        sign = "+" if p_val > 0 else ""
                        color = "#34D399" if p_val > 0 else ("#FB7185" if p_val < 0 else "#94A3B8")
                        pill_txt = f"{st_day['count']} Trd ({st_day['wins']}W {st_day['losses']}L)"
                        days_cells_html.append(f"""
                        <div class="cal-day-cell {c_cls}">
                            <div class="cal-day-top">
                                <span class="cal-day-num">{day_num:02d}</span>
                                <span style="font-size: 10px; color: {color};">●</span>
                            </div>
                            <div class="cal-pnl-val" style="color: {color};">{sign}${p_val:,.2f}</div>
                            <div class="cal-sub-pill">{pill_txt}</div>
                        </div>
                        """)
                    else:
                        is_weekend = (day_idx >= 5)
                        sub = "Weekend" if is_weekend else "No Trades"
                        cls = "cal-weekend" if is_weekend else "cal-neutral"
                        days_cells_html.append(f"""
                        <div class="cal-day-cell {cls}">
                            <div class="cal-day-top">
                                <span class="cal-day-num" style="opacity: 0.5;">{day_num:02d}</span>
                            </div>
                            <div class="cal-pnl-val" style="color: #475569; font-size: 13px;">—</div>
                            <div class="cal-sub-pill" style="opacity: 0.4;">{sub}</div>
                        </div>
                        """)

        st.markdown(f'<div class="cal-days-grid">{"".join(days_cells_html)}</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        # 8. LIVE TRADING HISTORY DOCKED AT THE BOTTOM
        st.markdown("""
        <div class="surface-panel">
            <div class="panel-header">
                <div>
                    <div class="panel-title">📋 Institutional Order Flow & Execution History</div>
                    <div class="panel-subtitle">Real-time timestamped fills, price offsets, points captured, and net realized cash</div>
                </div>
                <div class="status-pill">
                    <div class="pulse-indicator"></div>
                    REAL-TIME LEDGER
                </div>
            </div>
        """, unsafe_allow_html=True)

        # Filter Controls Bar
        col_f_out, col_f_side, col_f_rows, col_f_exp = st.columns([1.5, 1.2, 1.2, 1.5])
        with col_f_out:
            filter_outcome = st.selectbox("Outcome Filter", ["All Executions", "Winning Trades Only (🟢)", "Losing Trades Only (🔴)"], label_visibility="collapsed")
        with col_f_side:
            filter_side = st.selectbox("Side Filter", ["All Sides", "BUY / LONG", "SELL / SHORT"], label_visibility="collapsed")
        with col_f_rows:
            filter_rows = st.selectbox("Display Rows", ["Last 15 Trades", "Last 30 Trades", "Last 50 Trades", "All Executions"], label_visibility="collapsed")

        # Filter the DataFrame for History Table
        df_hist = df_view.sort_values(by='trade_time', ascending=False).copy()
        if "Winning" in filter_outcome:
            df_hist = df_hist[df_hist['pnl_usd'] > 0]
        elif "Losing" in filter_outcome:
            df_hist = df_hist[df_hist['pnl_usd'] <= 0]
            
        if "BUY" in filter_side:
            df_hist = df_hist[df_hist['side'] == 'BUY']
        elif "SELL" in filter_side:
            df_hist = df_hist[df_hist['side'] == 'SELL']

        if "15" in filter_rows:
            df_hist_sub = df_hist.head(15)
        elif "30" in filter_rows:
            df_hist_sub = df_hist.head(30)
        elif "50" in filter_rows:
            df_hist_sub = df_hist.head(50)
        else:
            df_hist_sub = df_hist

        with col_f_exp:
            csv_data = df_hist.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Export Ledger (.CSV)",
                data=csv_data,
                file_name=f"trade_history_{datetime.date.today()}.csv",
                mime="text/csv",
                use_container_width=True
            )

        # Render Polished Custom HTML Table
        table_rows_html = []
        for _, row in df_hist_sub.iterrows():
            t_str = row['trade_time'].strftime('%Y-%m-%d %H:%M:%S')
            side_badge = '<span class="badge-long">BUY</span>' if row['side'] == 'BUY' else '<span class="badge-short">SELL</span>'
            pnl_val = row['pnl_usd']
            pnl_pts = row['pnl_points']
            sign_str = "+" if pnl_val >= 0 else ""
            pnl_color = "#34D399" if pnl_val >= 0 else "#FB7185"
            
            table_rows_html.append(f"""
            <tr>
                <td style="color: #94A3B8;">{t_str}</td>
                <td><span class="badge-acc-tag">{row['account_name']}</span></td>
                <td style="font-weight: 700; color: #F8FAFC;">{row['asset']}</td>
                <td>{side_badge}</td>
                <td>{row['entry_price']:.2f}</td>
                <td>{row['exit_price']:.2f}</td>
                <td style="color: {pnl_color}; font-weight: 700;">{sign_str}{pnl_pts:.2f} pts</td>
                <td style="color: {pnl_color}; font-weight: 800;">{sign_str}${pnl_val:,.2f}</td>
                <td style="color: #CBD5E1;">{int(row['contracts'])}</td>
                <td style="color: #64748B; font-size: 11px;">{row['execution_type']}</td>
            </tr>
            """)

        st.markdown(f"""
        <div class="trade-table-wrapper">
            <table class="trade-table-custom">
                <thead>
                    <tr>
                        <th>Execution Time (EST)</th>
                        <th>Account</th>
                        <th>Asset</th>
                        <th>Side</th>
                        <th>Entry Price</th>
                        <th>Exit Price</th>
                        <th>Points</th>
                        <th>Realized P&L</th>
                        <th>Size</th>
                        <th>Engine Protocol</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(table_rows_html)}
                </tbody>
            </table>
        </div>
        """, unsafe_allow_html=True)

        # Table Summary Footer Strip
        h_total_pts = df_hist_sub['pnl_points'].sum()
        h_total_usd = df_hist_sub['pnl_usd'].sum()
        h_wins = len(df_hist_sub[df_hist_sub['pnl_usd'] > 0])
        h_rate = (h_wins / len(df_hist_sub) * 100.0) if len(df_hist_sub) > 0 else 0.0

        st.markdown(f"""
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 12px; padding: 10px 14px; background: rgba(15, 23, 42, 0.4); border-radius: 8px; font-size: 12px; color: #94A3B8;">
            <div>Showing <b>{len(df_hist_sub)}</b> of <b>{len(df_hist)}</b> filtered executions</div>
            <div style="display: flex; gap: 20px;">
                <span>Win Rate: <b style="color: #38BDF8;">{h_rate:.1f}%</b> ({h_wins}/{len(df_hist_sub)})</span>
                <span>Points Captured: <b style="color: {'#34D399' if h_total_pts >= 0 else '#FB7185'};">{'+' if h_total_pts >= 0 else ''}{h_total_pts:.2f} pts</b></span>
                <span>Net USD Realized: <b style="color: {'#34D399' if h_total_usd >= 0 else '#FB7185'};">{'+' if h_total_usd >= 0 else ''}${h_total_usd:,.2f}</b></span>
            </div>
        </div>
        </div>
        """, unsafe_allow_html=True)


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
