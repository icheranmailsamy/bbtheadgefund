import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os

st.set_page_config(page_title="Institutional Dashboard | 50% Equilibrium", layout="wide")

st.title("⚡ 50% Equilibrium Quant Dashboard")
st.markdown("Live multi-account monitoring and quantitative equity curves.")

DB_PATH = "trades.db"

# Initialize DB if it doesn't exist
if not os.path.exists(DB_PATH):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS trades
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  account_name TEXT,
                  trade_time TEXT,
                  asset TEXT,
                  type TEXT,
                  pnl_usd REAL)''')
    conn.commit()
    conn.close()

def load_data():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM trades", conn)
    conn.close()
    if not df.empty:
        df['trade_time'] = pd.to_datetime(df['trade_time'])
    return df

df = load_data()

if df.empty:
    st.info("No live trades recorded yet. Start the bot.py engine to stream trades.")
else:
    # Sidebar Filters
    account_list = df['account_name'].unique().tolist()
    selected_accounts = st.sidebar.multiselect("Select Prop Firm Accounts", account_list, default=account_list)
    
    filtered_df = df[df['account_name'].isin(selected_accounts)].copy()
    
    # Calculate Live Metrics
    filtered_df['cumulative_pnl'] = filtered_df['pnl_usd'].cumsum()
    filtered_df['peak'] = filtered_df['cumulative_pnl'].cummax()
    filtered_df['drawdown'] = filtered_df['cumulative_pnl'] - filtered_df['peak']
    
    total_profit = filtered_df['pnl_usd'].sum()
    max_dd = filtered_df['drawdown'].min()
    win_rate = (len(filtered_df[filtered_df['pnl_usd'] > 0]) / len(filtered_df)) * 100 if len(filtered_df) > 0 else 0
    total_trades = len(filtered_df)
    
    # Render Top Metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Net Profit", f"${total_profit:,.2f}")
    col2.metric("Max Drawdown ($)", f"${max_dd:,.2f}")
    col3.metric("Win Rate", f"{win_rate:.2f}%")
    col4.metric("Total Executions", f"{total_trades}")
    
    # Plotly Equity Curve
    st.subheader("Live Equity Curve")
    fig = px.line(filtered_df, x='trade_time', y='cumulative_pnl', title="Aggregated PnL", 
                  color_discrete_sequence=['#00FFAA'], template='plotly_dark')
    fig.update_layout(yaxis_title="Total Profit ($)", xaxis_title="Time")
    st.plotly_chart(fig, use_container_width=True)
    
    # Trade History Table
    st.subheader("Raw Trade Log")
    st.dataframe(filtered_df.sort_values(by='trade_time', ascending=False), use_container_width=True)
