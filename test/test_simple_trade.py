import warnings
warnings.filterwarnings('ignore')

import os
import sys
import time
import hashlib
import hmac
import requests
from datetime import datetime
from dotenv import load_dotenv

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

class SimpleTrader:
    def __init__(self):
        self.api_key = os.getenv("WALLET_A_API_KEY")
        self.api_secret = os.getenv("WALLET_A_API_SECRET")

        if not self.api_key or not self.api_secret:
            raise ValueError("API credentials not found. Please check your .env file.")

        self.base_url = "https://fapi.asterdex.com"
        print(f"✅ API credentials loaded")
        print(f"   API Key: {self.api_key[:10]}...")

    def _generate_signature(self, params):
        """Generate HMAC SHA256 signature"""
        # Remove signature if already present
        if 'signature' in params:
            del params['signature']
        # Create query string without sorting
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def _make_request(self, method, endpoint, params=None, signed=False):
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
                response = requests.get(url, params=params, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, params=params, headers=headers, timeout=30)
            else:
                raise ValueError(f"Unsupported method: {method}")

            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ API request failed: {e}")
            if hasattr(e.response, 'text'):
                print(f"   Response: {e.response.text}")
            return None

    def get_price(self, symbol):
        """Get current market price"""
        result = self._make_request('GET', '/fapi/v1/ticker/price', {'symbol': symbol})
        if result:
            return float(result['price'])
        return None

    def get_balance(self):
        """Get USDT balance"""
        result = self._make_request('GET', '/fapi/v2/account', signed=True)
        if result and 'assets' in result:
            for asset in result['assets']:
                if asset['asset'] == 'USDT':
                    return float(asset['availableBalance'])
        return None

    def place_market_order(self, symbol, side, quantity):
        """Place a market order"""
        params = {
            'symbol': symbol,
            'side': side,
            'type': 'MARKET',
            'quantity': quantity
        }
        return self._make_request('POST', '/fapi/v1/order', params, signed=True)

    def run_test(self):
        """Run the test trade"""
        symbol = "BTCUSDT"
        position_size_usdt = 100
        hold_time = 10

        print("\n" + "="*50)
        print("🚀 Starting Simple Trade Test")
        print("="*50)

        # 1. Check balance
        print("\n1️⃣  Checking account balance...")
        balance = self.get_balance()
        if balance:
            print(f"   Balance: ${balance:.2f} USDT")
        else:
            print("   ❌ Failed to get balance")
            return

        # 2. Get current price
        print("\n2️⃣  Getting BTC price...")
        price = self.get_price(symbol)
        if price:
            print(f"   BTC Price: ${price:,.2f}")
        else:
            print("   ❌ Failed to get price")
            return

        # 3. Calculate position size
        # BTC usually requires 3 decimal places for quantity
        quantity = round(position_size_usdt / price, 3)
        print(f"\n3️⃣  Calculating position size...")
        print(f"   Position: {quantity:.3f} BTC (${position_size_usdt} USDT)")

        # 4. Open long position
        print(f"\n4️⃣  Opening LONG position...")
        open_order = self.place_market_order(symbol, 'BUY', quantity)
        if open_order:
            print(f"   ✅ Long position opened")
            print(f"   Order ID: {open_order.get('orderId', 'N/A')}")
            if 'avgPrice' in open_order:
                print(f"   Fill Price: ${float(open_order['avgPrice']):,.2f}")
        else:
            print("   ❌ Failed to open position")
            return

        # 5. Hold position
        print(f"\n5️⃣  Holding position for {hold_time} seconds...")
        for i in range(hold_time, 0, -1):
            print(f"   {i}...", end='', flush=True)
            time.sleep(1)
        print()

        # 6. Close position
        print(f"\n6️⃣  Closing position...")
        close_order = self.place_market_order(symbol, 'SELL', quantity)
        if close_order:
            print(f"   ✅ Position closed")
            print(f"   Order ID: {close_order.get('orderId', 'N/A')}")
            if 'avgPrice' in close_order:
                print(f"   Fill Price: ${float(close_order['avgPrice']):,.2f}")
        else:
            print("   ❌ Failed to close position")

        # 7. Final balance
        print(f"\n7️⃣  Checking final balance...")
        final_balance = self.get_balance()
        if final_balance:
            print(f"   Final Balance: ${final_balance:.2f} USDT")
            pnl = final_balance - balance
            print(f"   P&L: ${pnl:+.2f} USDT")
        else:
            print("   ❌ Failed to get final balance")

        print("\n" + "="*50)
        print("✅ Test completed!")
        print("="*50)


if __name__ == "__main__":
    try:
        trader = SimpleTrader()
        trader.run_test()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()