from .storage import get_accounts, log_trade_record
import datetime

class BrokerMultiAccountRouter:
    """
    Trade & Order Router:
    - Queries active accounts from storage
    - Dispatches orders concurrently
    - Calculates USD PnL per account
    - Persists trade history to SQLite
    """
    def __init__(self, asset="MNQ"):
        self.asset = asset
        self.pt_value = 2.00 if asset == "MNQ" else 5.00

    def dispatch_entry(self, signal):
        accounts_df = get_accounts()
        active_accounts = accounts_df[accounts_df['is_active'] == 1]
        
        dispatched = []
        for _, acc in active_accounts.iterrows():
            # In live production: POST to Tradovate / Rithmic API
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

        for _, acc in active_accounts.iterrows():
            contracts = int(acc['contracts'])
            pnl_usd = pts * self.pt_value * contracts
            
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
