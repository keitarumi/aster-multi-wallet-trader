import warnings
warnings.filterwarnings('ignore')

import requests
import time
from datetime import datetime

BASE_URL = "https://fapi.asterdex.com"

def get_ticker_price(symbol):
    """Get current price for a symbol"""
    endpoint = f"{BASE_URL}/fapi/v1/ticker/price"
    params = {"symbol": symbol}

    try:
        response = requests.get(endpoint, params=params)
        response.raise_for_status()
        data = response.json()
        return float(data['price'])
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {symbol}: {e}")
        return None
    except (KeyError, ValueError) as e:
        print(f"Error parsing {symbol} data: {e}")
        return None

def main():
    print("Starting price tracker for BTC, ETH, ASTER, and SOL...", flush=True)
    print("-" * 70, flush=True)

    while True:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        btc_price = get_ticker_price("BTCUSDT")
        eth_price = get_ticker_price("ETHUSDT")
        aster_price = get_ticker_price("ASTERUSDT")
        sol_price = get_ticker_price("SOLUSDT")

        prices = []
        if btc_price:
            prices.append(f"BTC: ${btc_price:,.2f}")
        if eth_price:
            prices.append(f"ETH: ${eth_price:,.2f}")
        if aster_price:
            prices.append(f"ASTER: ${aster_price:,.4f}")
        if sol_price:
            prices.append(f"SOL: ${sol_price:,.2f}")

        if prices:
            print(f"[{timestamp}] {' | '.join(prices)}", flush=True)
        else:
            print(f"[{timestamp}] Failed to fetch any prices", flush=True)

        time.sleep(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nPrice tracker stopped.")