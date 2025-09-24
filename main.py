#!/usr/bin/env python3
"""
Aster Multi-Wallet Trading System
Main entry point
"""
import sys
import os
import argparse

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from multi_wallet_trader import MultiWalletTrader
from discord_reporter import DiscordReporter


def main():
    parser = argparse.ArgumentParser(description='Aster Multi-Wallet Trading System')
    parser.add_argument('command', choices=['trade', 'report', 'test'],
                       help='Command to execute')
    parser.add_argument('--config', default='config.yaml',
                       help='Configuration file path')
    parser.add_argument('--test-mode', action='store_true',
                       help='Run in test mode (single trade then exit)')

    args = parser.parse_args()

    if args.command == 'trade':
        # Start trading system
        trader = MultiWalletTrader(args.config)
        if args.test_mode:
            print("Running in test mode...")
            trader.execute_trading_round()
            print("Test trade completed.")
        else:
            trader.run()

    elif args.command == 'report':
        # Run Discord reporter
        reporter = DiscordReporter(args.config)
        if args.test_mode:
            reporter.send_balance_report()
        else:
            reporter.run()

    elif args.command == 'test':
        # Quick system test
        print("Testing system configuration...")
        try:
            trader = MultiWalletTrader(args.config)
            print(f"✅ Wallets detected: {len(trader.wallets)}")
            print(f"✅ Symbols configured: {', '.join(trader.symbols)}")
            print(f"✅ Database connected")

            for wallet_id, wallet in trader.wallets.items():
                balance = wallet.get_account_balance()
                if balance:
                    print(f"✅ {wallet.name}: ${balance:.2f} USDT")

            trader.db_manager.close()
            print("\n✅ All systems operational!")
        except Exception as e:
            print(f"❌ System test failed: {e}")
            sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nShutdown requested. Exiting...")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)