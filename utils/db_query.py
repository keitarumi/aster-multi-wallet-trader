#!/usr/bin/env python3
import sys
import os
import argparse
from datetime import datetime, timedelta

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

from database_manager import DatabaseManager
from colorama import init, Fore, Style
import pandas as pd

init(autoreset=True)


def print_header(title: str):
    """Print a formatted header"""
    print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{title.center(60)}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")


def show_statistics(db):
    """Show overall trading statistics"""
    print_header("📊 Trading Statistics")

    stats = db.get_statistics()

    print(f"{Fore.GREEN}Trading Overview:{Style.RESET_ALL}")
    print(f"  Total Trades: {stats.get('total_trades', 0)}")
    print(f"  Total Positions: {stats.get('total_positions', 0)}")
    print(f"  Open Positions: {stats.get('open_positions', 0)}")
    print(f"  Closed Positions: {stats.get('total_positions', 0) - stats.get('open_positions', 0)}")

    print(f"\n{Fore.YELLOW}Performance:{Style.RESET_ALL}")
    print(f"  Total PnL: ${stats.get('total_pnl', 0):.2f}")
    print(f"  Success Rate: {stats.get('success_rate', 0):.1f}%")

    if 'most_traded_symbol' in stats:
        print(f"\n{Fore.BLUE}Most Traded:{Style.RESET_ALL}")
        print(f"  Symbol: {stats['most_traded_symbol']}")
        print(f"  Trade Count: {stats['most_traded_count']}")


def show_recent_trades(db, limit: int = 20):
    """Show recent trade history"""
    print_header(f"📈 Recent Trades (Last {limit})")

    trades = db.get_trade_history(limit=limit)

    if not trades:
        print("No trades found.")
        return

    for trade in trades:
        timestamp = trade.get('timestamp', 'N/A')
        symbol = trade.get('symbol', 'N/A')
        side = trade.get('side', 'N/A')
        quantity = trade.get('quantity', 0)
        wallet = trade.get('wallet_name', 'N/A')
        status = trade.get('status', 'N/A')

        side_color = Fore.GREEN if side == 'BUY' else Fore.RED
        status_color = Fore.GREEN if status == 'SUCCESS' else Fore.RED

        print(f"[{timestamp}] {symbol:10} {side_color}{side:4}{Style.RESET_ALL} "
              f"Qty: {quantity:8.3f} Wallet: {wallet:15} "
              f"Status: {status_color}{status}{Style.RESET_ALL}")


def show_positions(db, status: str = None, limit: int = 20):
    """Show position history"""
    if status:
        print_header(f"📊 {status.title()} Positions (Last {limit})")
    else:
        print_header(f"📊 All Positions (Last {limit})")

    positions = db.get_position_history(status=status, limit=limit)

    if not positions:
        print("No positions found.")
        return

    for pos in positions:
        symbol = pos.get('symbol', 'N/A')
        wallet_long = pos.get('wallet_long', 'N/A')
        wallet_short = pos.get('wallet_short', 'N/A')
        quantity = pos.get('quantity', 0)
        status_val = pos.get('status', 'N/A')
        open_time = pos.get('open_time', 'N/A')
        close_time = pos.get('close_time', 'N/A')
        pnl = pos.get('total_pnl', 0)

        status_color = Fore.GREEN if status_val == 'OPEN' else Fore.YELLOW
        pnl_color = Fore.GREEN if pnl >= 0 else Fore.RED

        print(f"\n{status_color}[{status_val}]{Style.RESET_ALL} {symbol}")
        print(f"  Long: {wallet_long} | Short: {wallet_short}")
        print(f"  Quantity: {quantity:.3f}")
        print(f"  Open: {open_time}")

        if status_val == 'CLOSED':
            print(f"  Close: {close_time}")
            print(f"  PnL: {pnl_color}${pnl:.2f}{Style.RESET_ALL}")


def show_daily_summary(db, date: str = None):
    """Show daily trading summary"""
    if not date:
        date = datetime.now().strftime('%Y-%m-%d')

    print_header(f"📅 Daily Summary - {date}")

    summary = db.get_daily_summary(date)

    if not summary:
        print("No data available for this date.")
        return

    print(f"{Fore.GREEN}Trading Activity:{Style.RESET_ALL}")
    print(f"  Total Trades: {summary.get('total_trades', 0)}")
    print(f"  Total Volume: ${summary.get('total_volume', 0):.2f}")
    print(f"  Unique Symbols: {summary.get('unique_symbols', 0)}")
    print(f"  Active Wallets: {summary.get('active_wallets', 0)}")

    daily_pnl = summary.get('daily_pnl', 0)
    pnl_color = Fore.GREEN if daily_pnl >= 0 else Fore.RED
    print(f"\n{Fore.YELLOW}Performance:{Style.RESET_ALL}")
    print(f"  Daily PnL: {pnl_color}${daily_pnl:.2f}{Style.RESET_ALL}")


def export_to_csv(db, export_type: str, filename: str = None):
    """Export data to CSV file"""
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{export_type}_{timestamp}.csv"

    if export_type == 'trades':
        data = db.get_trade_history(limit=10000)
        df = pd.DataFrame(data)
        df.to_csv(filename, index=False)
        print(f"{Fore.GREEN}✅ Exported trades to {filename}{Style.RESET_ALL}")

    elif export_type == 'positions':
        data = db.get_position_history(limit=10000)
        df = pd.DataFrame(data)
        df.to_csv(filename, index=False)
        print(f"{Fore.GREEN}✅ Exported positions to {filename}{Style.RESET_ALL}")

    else:
        print(f"{Fore.RED}❌ Unknown export type: {export_type}{Style.RESET_ALL}")


def cleanup_database(db, days: int):
    """Clean up old records from database"""
    print_header(f"🗑️ Database Cleanup")

    print(f"Removing records older than {days} days...")
    deleted = db.cleanup_old_records(days)
    print(f"{Fore.GREEN}✅ Deleted {deleted} old records{Style.RESET_ALL}")


def main():
    parser = argparse.ArgumentParser(description='Query and analyze trading database')
    parser.add_argument('command', choices=['stats', 'trades', 'positions', 'open', 'closed', 'daily', 'export', 'cleanup'],
                       help='Command to execute')
    parser.add_argument('--limit', type=int, default=20, help='Number of records to show')
    parser.add_argument('--date', type=str, help='Date for daily summary (YYYY-MM-DD)')
    parser.add_argument('--export-type', choices=['trades', 'positions'], help='Type of data to export')
    parser.add_argument('--output', type=str, help='Output filename for export')
    parser.add_argument('--days', type=int, default=30, help='Days to keep for cleanup')
    parser.add_argument('--db', type=str, default='data/trades.db', help='Database file path')

    args = parser.parse_args()

    # Initialize database
    db = DatabaseManager(args.db)

    try:
        if args.command == 'stats':
            show_statistics(db)

        elif args.command == 'trades':
            show_recent_trades(db, limit=args.limit)

        elif args.command == 'positions':
            show_positions(db, limit=args.limit)

        elif args.command == 'open':
            show_positions(db, status='OPEN', limit=args.limit)

        elif args.command == 'closed':
            show_positions(db, status='CLOSED', limit=args.limit)

        elif args.command == 'daily':
            show_daily_summary(db, date=args.date)

        elif args.command == 'export':
            if not args.export_type:
                print(f"{Fore.RED}❌ Please specify --export-type (trades or positions){Style.RESET_ALL}")
            else:
                export_to_csv(db, args.export_type, args.output)

        elif args.command == 'cleanup':
            cleanup_database(db, args.days)

    finally:
        db.close()


if __name__ == "__main__":
    main()