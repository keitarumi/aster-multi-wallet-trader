import warnings
warnings.filterwarnings('ignore')

import yaml
import time
import random
import hashlib
import hmac
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from colorama import init, Fore, Style
from dotenv import load_dotenv

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

init(autoreset=True)
load_dotenv()

class WalletManager:
    def __init__(self, wallet_id: str, wallet_config: dict):
        env_prefix = wallet_id.upper()
        self.api_key = os.getenv(f"{env_prefix}_API_KEY")
        self.api_secret = os.getenv(f"{env_prefix}_API_SECRET")

        if not self.api_key or not self.api_secret:
            raise ValueError(f"API credentials not found for {wallet_id}. Please check your .env file.")

        self.name = wallet_config['name']
        self.base_url = "https://fapi.asterdex.com"
        self.timeout = 30

    def _generate_signature(self, params: dict) -> str:
        """Generate HMAC SHA256 signature for API requests"""
        if 'signature' in params:
            del params['signature']
        # Don't sort params - use them in order
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def _make_request(self, method: str, endpoint: str, params: dict = None, signed: bool = False) -> dict:
        """Make API request"""
        url = f"{self.base_url}{endpoint}"

        if params is None:
            params = {}

        if signed:
            params['timestamp'] = int(time.time() * 1000)
            params['recvWindow'] = 5000
            params['signature'] = self._generate_signature(params)

        headers = {}
        if signed:
            headers['X-MBX-APIKEY'] = self.api_key

        try:
            if method == 'GET':
                response = requests.get(url, params=params, headers=headers, timeout=self.timeout)
            elif method == 'POST':
                response = requests.post(url, params=params, headers=headers, timeout=self.timeout)
            else:
                raise ValueError(f"Unsupported method: {method}")

            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"API request failed for {self.name}: {e}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                logging.error(f"Response: {e.response.text}")
            return None

    def get_account_balance(self) -> Optional[float]:
        """Get USDT balance"""
        result = self._make_request('GET', '/fapi/v2/account', signed=True)
        if result and 'assets' in result:
            for asset in result['assets']:
                if asset['asset'] == 'USDT':
                    return float(asset['availableBalance'])
        return None

    def place_order(self, symbol: str, side: str, quantity: float) -> Optional[dict]:
        """Place market order"""
        params = {
            'symbol': symbol,
            'side': side,
            'type': 'MARKET',
            'quantity': quantity
        }
        return self._make_request('POST', '/fapi/v1/order', params, signed=True)

    def close_position(self, symbol: str, side: str, quantity: float) -> Optional[dict]:
        """Close position with opposite market order"""
        close_side = 'SELL' if side == 'BUY' else 'BUY'
        return self.place_order(symbol, close_side, quantity)


import requests

class TwoWalletTester:
    def __init__(self):
        # Load config
        with open('config.yaml', 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        # Initialize only wallets A and B
        self.wallets = {}
        for wallet_id in ['wallet_A', 'wallet_B']:
            try:
                self.wallets[wallet_id] = WalletManager(wallet_id, self.config['wallets'][wallet_id])
                print(f"✅ Initialized {self.config['wallets'][wallet_id]['name']}")
            except ValueError as e:
                print(f"❌ Failed to initialize {wallet_id}: {e}")
                exit(1)

        self.delay = self.config['trading_params']['wallet_execution_delay']

    def _get_current_price(self, symbol: str) -> Optional[float]:
        """Get current market price"""
        url = f"https://fapi.asterdex.com/fapi/v1/ticker/price"
        try:
            response = requests.get(url, params={'symbol': symbol}, timeout=10)
            response.raise_for_status()
            return float(response.json()['price'])
        except Exception as e:
            print(f"❌ Failed to get price for {symbol}: {e}")
            return None

    def calculate_position_size(self, symbol: str) -> float:
        """Calculate position size with variance"""
        base_size = self.config['trading_params']['base_position_size_usdt']
        variance = self.config['trading_params']['position_size_variance']

        price = self._get_current_price(symbol)
        if not price:
            return 0

        size_usdt = base_size * (1 + random.uniform(-variance, variance))

        # Adjust precision based on symbol
        if 'BTC' in symbol:
            quantity = round(size_usdt / price, 3)  # 3 decimals for BTC
        else:
            quantity = round(size_usdt / price, 4)  # 4 decimals for others

        return quantity

    def run_test(self):
        """Run two-wallet hedge test"""
        print("\n" + "="*60)
        print(f"{Fore.CYAN}🚀 Starting Two-Wallet Hedge Test{Style.RESET_ALL}")
        print("="*60)

        symbol = "BTCUSDT"
        wallet_a = self.wallets['wallet_A']
        wallet_b = self.wallets['wallet_B']

        # 1. Check balances
        print(f"\n1️⃣  {Fore.YELLOW}Checking account balances...{Style.RESET_ALL}")
        balance_a = wallet_a.get_account_balance()
        balance_b = wallet_b.get_account_balance()

        if balance_a:
            print(f"   {wallet_a.name}: ${balance_a:.2f} USDT")
        else:
            print(f"   ❌ Failed to get balance for {wallet_a.name}")
            return

        if balance_b:
            print(f"   {wallet_b.name}: ${balance_b:.2f} USDT")
        else:
            print(f"   ❌ Failed to get balance for {wallet_b.name}")
            return

        # 2. Get price and calculate position
        print(f"\n2️⃣  {Fore.YELLOW}Getting BTC price...{Style.RESET_ALL}")
        price = self._get_current_price(symbol)
        if price:
            print(f"   BTC Price: ${price:,.2f}")
        else:
            print("   ❌ Failed to get price")
            return

        quantity = self.calculate_position_size(symbol)
        position_value = quantity * price
        print(f"   Position: {quantity:.4f} BTC (≈${position_value:.2f} USDT)")

        # 3. Open hedge positions with delay
        print(f"\n3️⃣  {Fore.GREEN}Opening hedge positions...{Style.RESET_ALL}")

        # Wallet A opens LONG
        print(f"   Opening LONG on {wallet_a.name}...")
        order_a = wallet_a.place_order(symbol, 'BUY', quantity)
        if order_a:
            print(f"   ✅ {wallet_a.name}: LONG {quantity} BTC opened")
        else:
            print(f"   ❌ Failed to open LONG on {wallet_a.name}")
            return

        # Wait for delay
        print(f"   Waiting {self.delay}s before opening opposite position...")
        time.sleep(self.delay)

        # Wallet B opens SHORT
        print(f"   Opening SHORT on {wallet_b.name}...")
        order_b = wallet_b.place_order(symbol, 'SELL', quantity)
        if order_b:
            print(f"   ✅ {wallet_b.name}: SHORT {quantity} BTC opened")
        else:
            print(f"   ❌ Failed to open SHORT on {wallet_b.name}")
            # Close wallet A position
            wallet_a.close_position(symbol, 'BUY', quantity)
            return

        # 4. Hold positions
        hold_time = 60  # 1 minute for test
        print(f"\n4️⃣  {Fore.CYAN}Holding positions for {hold_time} seconds...{Style.RESET_ALL}")
        for i in range(hold_time, 0, -10):
            print(f"   {i}s remaining...", end='', flush=True)
            time.sleep(10 if i >= 10 else i)
        print()

        # 5. Close positions with delay
        print(f"\n5️⃣  {Fore.YELLOW}Closing positions...{Style.RESET_ALL}")

        # Close wallet A first
        print(f"   Closing LONG on {wallet_a.name}...")
        close_a = wallet_a.close_position(symbol, 'BUY', quantity)
        if close_a:
            print(f"   ✅ {wallet_a.name}: LONG closed")
        else:
            print(f"   ❌ Failed to close LONG on {wallet_a.name}")

        # Wait for delay
        print(f"   Waiting {self.delay}s before closing opposite position...")
        time.sleep(self.delay)

        # Close wallet B
        print(f"   Closing SHORT on {wallet_b.name}...")
        close_b = wallet_b.close_position(symbol, 'SELL', quantity)
        if close_b:
            print(f"   ✅ {wallet_b.name}: SHORT closed")
        else:
            print(f"   ❌ Failed to close SHORT on {wallet_b.name}")

        # 6. Check final balances
        print(f"\n6️⃣  {Fore.YELLOW}Checking final balances...{Style.RESET_ALL}")
        final_balance_a = wallet_a.get_account_balance()
        final_balance_b = wallet_b.get_account_balance()

        if final_balance_a:
            pnl_a = final_balance_a - balance_a
            print(f"   {wallet_a.name}: ${final_balance_a:.2f} (P&L: ${pnl_a:+.2f})")

        if final_balance_b:
            pnl_b = final_balance_b - balance_b
            print(f"   {wallet_b.name}: ${final_balance_b:.2f} (P&L: ${pnl_b:+.2f})")

        if final_balance_a and final_balance_b:
            total_pnl = pnl_a + pnl_b
            print(f"   {Fore.CYAN}Total P&L: ${total_pnl:+.2f}{Style.RESET_ALL}")

        print("\n" + "="*60)
        print(f"{Fore.GREEN}✅ Test completed!{Style.RESET_ALL}")
        print("="*60)


if __name__ == "__main__":
    try:
        tester = TwoWalletTester()
        tester.run_test()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()