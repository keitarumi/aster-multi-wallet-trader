import os
import sys
import os
import sys
from dotenv import load_dotenv
from colorama import init, Fore, Style

# Add parent directory to path

init(autoreset=True)
load_dotenv()

def test_wallet_detection():
    """Test automatic wallet detection from .env file"""
    print("\n" + "="*60)
    print(f"{Fore.CYAN}🔍 Testing Automatic Wallet Detection{Style.RESET_ALL}")
    print("="*60)

    # Find all wallet IDs from environment variables
    wallet_pattern = 'WALLET_'
    detected_wallets = {}

    for env_key in os.environ.keys():
        if env_key.startswith(wallet_pattern) and env_key.endswith('_API_KEY'):
            # Extract wallet identifier (e.g., WALLET_A from WALLET_A_API_KEY)
            wallet_id = env_key.replace('_API_KEY', '')

            # Check if corresponding secret exists
            secret_key = f"{wallet_id}_API_SECRET"
            if secret_key in os.environ:
                api_key = os.environ[env_key]
                api_secret = os.environ[secret_key]

                detected_wallets[wallet_id] = {
                    'api_key': api_key[:20] + '...' if len(api_key) > 20 else api_key,
                    'api_secret': api_secret[:20] + '...' if len(api_secret) > 20 else api_secret,
                    'name': wallet_id.replace('_', ' ').title()
                }

    # Display results
    if detected_wallets:
        print(f"\n✅ {Fore.GREEN}Found {len(detected_wallets)} wallet(s) in .env:{Style.RESET_ALL}")
        for wallet_id, info in sorted(detected_wallets.items()):
            print(f"\n   {Fore.YELLOW}{info['name']}:{Style.RESET_ALL}")
            print(f"      API Key: {info['api_key']}")
            print(f"      API Secret: {info['api_secret']}")
    else:
        print(f"\n❌ {Fore.RED}No wallets detected in .env file{Style.RESET_ALL}")
        print("\nExpected format in .env:")
        print("   WALLET_A_API_KEY=your_api_key")
        print("   WALLET_A_API_SECRET=your_api_secret")
        print("   WALLET_B_API_KEY=your_api_key")
        print("   WALLET_B_API_SECRET=your_api_secret")

    # Check if we have minimum required wallets
    print(f"\n{Fore.CYAN}Status Check:{Style.RESET_ALL}")
    if len(detected_wallets) >= 2:
        print(f"   ✅ Sufficient wallets for hedging (minimum 2 required)")
        print(f"   📊 Can create {len(list(combinations(detected_wallets.keys(), 2)))} unique pairs")
    elif len(detected_wallets) == 1:
        print(f"   ⚠️  Only 1 wallet detected - need at least 2 for hedging")
    else:
        print(f"   ❌ No wallets detected")

    # Show how to add more wallets
    if len(detected_wallets) < 4:
        print(f"\n{Fore.BLUE}To add more wallets:{Style.RESET_ALL}")
        next_letter = chr(ord('A') + len(detected_wallets))
        print(f"   Add to .env file:")
        print(f"   WALLET_{next_letter}_API_KEY=your_api_key")
        print(f"   WALLET_{next_letter}_API_SECRET=your_api_secret")

    print("\n" + "="*60)
    print(f"{Fore.GREEN}Test completed!{Style.RESET_ALL}")
    print("="*60)

    return detected_wallets

def test_multi_wallet_trader():
    """Test the MultiWalletTrader with auto-detection"""
    print(f"\n{Fore.CYAN}Testing MultiWalletTrader initialization...{Style.RESET_ALL}")

    try:
        import yaml
        import warnings
        warnings.filterwarnings('ignore')

        from multi_wallet_trader import MultiWalletTrader

        trader = MultiWalletTrader("config.yaml")

        print(f"\n{Fore.GREEN}✅ MultiWalletTrader initialized successfully!{Style.RESET_ALL}")
        print(f"   Active wallets: {len(trader.wallets)}")
        for wallet_id, wallet in trader.wallets.items():
            print(f"   - {wallet.name}")

    except Exception as e:
        print(f"\n{Fore.RED}❌ Error initializing MultiWalletTrader:{Style.RESET_ALL}")
        print(f"   {e}")

# Import combinations for pair counting
from itertools import combinations

if __name__ == "__main__":
    wallets = test_wallet_detection()

    if len(wallets) >= 2:
        test_multi_wallet_trader()