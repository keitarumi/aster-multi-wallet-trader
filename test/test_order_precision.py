import requests
import os
from dotenv import load_dotenv

load_dotenv()

# Test precision requirements for each symbol
symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "ASTERUSDT"]

for symbol in symbols:
    print(f"\n{symbol}:")

    # Get exchange info to check precision requirements
    url = "https://fapi.asterdex.com/fapi/v1/exchangeInfo"
    response = requests.get(url)

    if response.ok:
        data = response.json()
        for s in data['symbols']:
            if s['symbol'] == symbol:
                print(f"  Status: {s['status']}")

                # Find LOT_SIZE filter for quantity precision
                for f in s['filters']:
                    if f['filterType'] == 'LOT_SIZE':
                        print(f"  Min Qty: {f['minQty']}")
                        print(f"  Max Qty: {f['maxQty']}")
                        print(f"  Step Size: {f['stepSize']}")

                        # Calculate decimal places from stepSize
                        step = float(f['stepSize'])
                        if step >= 1:
                            decimals = 0
                        else:
                            decimals = len(str(step).split('.')[-1].rstrip('0'))
                        print(f"  Required decimals: {decimals}")

                    if f['filterType'] == 'MARKET_LOT_SIZE':
                        print(f"  Market Min Qty: {f.get('minQty', 'N/A')}")
                        print(f"  Market Max Qty: {f.get('maxQty', 'N/A')}")
                        print(f"  Market Step Size: {f.get('stepSize', 'N/A')}")

                break