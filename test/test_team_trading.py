#!/usr/bin/env python3
import sys
import os
"""
Test script for team-based trading system
"""
import sys
import os

import time
import logging
from multi_wallet_trader import MultiWalletTrader
from colorama import init, Fore, Style

init(autoreset=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_team_trading():
    """Test team-based trading functionality"""
    print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Team-Based Trading Test{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")

    # Initialize trader
    trader = MultiWalletTrader("config.yaml")

    # Show wallet configuration
    print(f"\n{Fore.GREEN}Available Wallets:{Style.RESET_ALL}")
    for wallet_id, wallet in trader.wallets.items():
        balance = wallet.get_account_balance()
        if balance:
            print(f"  {wallet.name}: ${balance:.2f} USDT")

    # Show team allocation examples
    print(f"\n{Fore.YELLOW}Team Allocation Examples:{Style.RESET_ALL}")
    available_wallets = list(trader.wallets.keys())

    for i in range(3):
        long_team, short_team = trader.split_wallets_into_teams(available_wallets)
        print(f"\nExample {i+1}:")
        print(f"  Long team ({len(long_team)}): {[trader.wallets[w].name for w in long_team]}")
        print(f"  Short team ({len(short_team)}): {[trader.wallets[w].name for w in short_team]}")

    # Test quantity distribution
    print(f"\n{Fore.YELLOW}Quantity Distribution Test:{Style.RESET_ALL}")
    test_symbol = 'BTCUSDT'
    total_quantity = trader.calculate_position_size(test_symbol)

    if total_quantity > 0:
        print(f"Total position size for {test_symbol}: {total_quantity}")

        # Test with different team sizes
        for team_size in [1, 2, 3, 4]:
            if team_size <= len(available_wallets):
                quantities = trader.distribute_quantity_in_teams(total_quantity, team_size, test_symbol)
                print(f"\nTeam size {team_size}:")
                print(f"  Quantities: {quantities}")
                print(f"  Sum: {sum(quantities):.3f} (should equal {total_quantity:.3f})")
                print(f"  Variance: {max(quantities)/min(quantities):.2f}x between max and min")

    # Ask user if they want to execute a real trade
    print(f"\n{Fore.MAGENTA}{'='*60}{Style.RESET_ALL}")
    response = input(f"{Fore.MAGENTA}Do you want to execute a REAL team-based trade? (yes/no): {Style.RESET_ALL}")

    if response.lower() == 'yes':
        print(f"\n{Fore.RED}Executing REAL team-based trade...{Style.RESET_ALL}")

        # Get available symbols
        available_symbols = trader.get_available_symbols()
        if available_symbols:
            symbol = available_symbols[0]
            print(f"Trading symbol: {symbol}")

            # Execute team-based trade
            success = trader.open_team_hedge_position(symbol)

            if success:
                print(f"\n{Fore.GREEN}✅ Team hedge position opened successfully!{Style.RESET_ALL}")
                print("Waiting 5 seconds before checking positions...")
                time.sleep(5)

                # Show active positions
                print(f"\n{Fore.CYAN}Active Positions:{Style.RESET_ALL}")
                for sym, positions in trader.active_positions.items():
                    print(f"\nSymbol: {sym}")
                    long_positions = [p for p in positions if p['side'] == 'BUY']
                    short_positions = [p for p in positions if p['side'] == 'SELL']

                    print(f"  Long team ({len(long_positions)}):")
                    for pos in long_positions:
                        wallet_name = trader.wallets[pos['wallet']].name
                        print(f"    {wallet_name}: {pos['quantity']}")

                    print(f"  Short team ({len(short_positions)}):")
                    for pos in short_positions:
                        wallet_name = trader.wallets[pos['wallet']].name
                        print(f"    {wallet_name}: {pos['quantity']}")

                # Ask if user wants to close positions
                close_response = input(f"\n{Fore.YELLOW}Close positions now? (yes/no): {Style.RESET_ALL}")
                if close_response.lower() == 'yes':
                    trader.close_all_positions()
                    print(f"{Fore.GREEN}✅ All positions closed.{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}❌ Failed to open team hedge position.{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}No available symbols for trading.{Style.RESET_ALL}")
    else:
        print(f"{Fore.YELLOW}Test completed without executing trades.{Style.RESET_ALL}")

    # Cleanup
    trader.db_manager.close()
    print(f"\n{Fore.GREEN}Test completed!{Style.RESET_ALL}")


if __name__ == "__main__":
    try:
        test_team_trading()
    except KeyboardInterrupt:
        print(f"\n{Fore.RED}Test interrupted by user.{Style.RESET_ALL}")
    except Exception as e:
        print(f"\n{Fore.RED}Error: {e}{Style.RESET_ALL}")
        import traceback
        traceback.print_exc()