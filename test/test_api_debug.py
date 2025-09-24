import os
import time
import hashlib
import hmac
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("WALLET_A_API_KEY")
api_secret = os.getenv("WALLET_A_API_SECRET")

print(f"API Key: {api_key[:20]}...")
print(f"API Secret: {api_secret[:20]}...")

# Test 1: Simple price request (no auth needed)
url = "https://fapi.asterdex.com/fapi/v1/ticker/price"
params = {"symbol": "BTCUSDT"}
response = requests.get(url, params=params)
print(f"\n1. Price test: {response.status_code}")
if response.ok:
    print(f"   BTC Price: ${response.json()['price']}")

# Test 2: Server time
url = "https://fapi.asterdex.com/fapi/v1/time"
response = requests.get(url)
print(f"\n2. Server time: {response.status_code}")
if response.ok:
    server_time = response.json()['serverTime']
    local_time = int(time.time() * 1000)
    diff = server_time - local_time
    print(f"   Server time: {server_time}")
    print(f"   Local time:  {local_time}")
    print(f"   Difference:  {diff}ms")

# Test 3: Account balance with signature
print(f"\n3. Testing account endpoint with signature...")

# Create params
params = {
    'timestamp': int(time.time() * 1000),
    'recvWindow': 5000
}

# Create query string
query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
print(f"   Query string: {query_string}")

# Generate signature
signature = hmac.new(
    api_secret.encode('utf-8'),
    query_string.encode('utf-8'),
    hashlib.sha256
).hexdigest()
print(f"   Signature: {signature}")

# Add signature to params
params['signature'] = signature

# Make request
url = "https://fapi.asterdex.com/fapi/v2/account"
headers = {'X-MBX-APIKEY': api_key}

response = requests.get(url, params=params, headers=headers)
print(f"\n   Response status: {response.status_code}")
print(f"   Response: {response.text[:500]}")