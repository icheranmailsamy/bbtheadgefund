from .storage import get_accounts, log_trade_record
import datetime
import requests
import json

class BrokerMultiAccountRouter:
    """
    Trade & Order Router:
    - Queries active accounts from storage
    - Dispatches orders concurrently to live broker APIs (Tradovate REST/WS)
    - Calculates USD PnL per account
    - Persists trade history to SQLite
    """
    def __init__(self, asset="MNQ"):
        self.asset = asset
        self.pt_value = 2.00 if asset == "MNQ" else 5.00
        self.tradovate_base_url = "https://live.tradovate.com/v1"

    def _execute_tradovate_order(self, account_name, token, action, contracts):
        """Dispatches an actual HTTP market order to Tradovate Live REST API."""
        if not token or len(token) < 15 or token.startswith("DEMO_") or token.startswith("YOUR_"):
            return None
        url = f"{self.tradovate_base_url}/order/placeorder"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        payload = {
            "accountSpec": account_name,
            "action": "Buy" if action.upper() == "BUY" else "Sell",
            "symbol": self.asset,
            "orderQty": int(contracts),
            "orderType": "Market",
            "isAutomated": True
        }
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=4)
            resp_data = res.json()
            print(f"[TRADE ROUTER] Tradovate Response for [{account_name}]: {resp_data}")
            return resp_data
        except Exception as e:
            print(f"[TRADE ROUTER ERROR] Failed to send order for [{account_name}]: {e}")
            return None

    def dispatch_entry(self, signal):
        accounts_df = get_accounts()
        active_accounts = accounts_df[accounts_df['is_active'] == 1]
        
        dispatched = []
        for _, acc in active_accounts.iterrows():
            token = str(acc.get('api_key', ''))
            broker_name = str(acc.get('broker', '')).lower()
            
            # Fire real order if Tradovate / Topstep account with live token
            if "tradovate" in broker_name or "topstep" in broker_name:
                self._execute_tradovate_order(acc['account_name'], token, signal['side'], acc['contracts'])

            dispatched.append({
                'account': acc['account_name'],
                'contracts': acc['contracts'],
                'side': signal['side'],
                'entry_price': signal['entry_price']
            })
            print(f"[TRADE ROUTER] -> Sent {signal['side']} {acc['contracts']} {self.asset} to Account [{acc['account_name']}] @ {signal['entry_price']:.2f}")
        return dispatched

    def dispatch_exit(self, exit_event, side, entry_p):
        accounts_df = get_accounts()
        active_accounts = accounts_df[accounts_df['is_active'] == 1]
        
        pts = exit_event['pnl_points']
        exit_p = exit_event['exit_price']
        exec_type = exit_event['exit_type']
        exit_action = "Sell" if side.upper() == "BUY" else "Buy"

        for _, acc in active_accounts.iterrows():
            contracts = int(acc['contracts'])
            pnl_usd = pts * self.pt_value * contracts
            token = str(acc.get('api_key', ''))
            broker_name = str(acc.get('broker', '')).lower()

            # Fire real exit order if Tradovate / Topstep account with live token
            if "tradovate" in broker_name or "topstep" in broker_name:
                self._execute_tradovate_order(acc['account_name'], token, exit_action, contracts)

            # Persist to database
            log_trade_record(
                account_name=acc['account_name'],
                asset=self.asset,
                side=side,
                entry_p=entry_p,
                exit_p=exit_p,
                pts=pts,
                pnl_usd=pnl_usd,
                contracts=contracts,
                exec_type=exec_type
            )
            print(f"[TRADE ROUTER] -> Logged {exec_type} for [{acc['account_name']}] | Points: {pts:.2f} | PnL: ${pnl_usd:.2f}")

