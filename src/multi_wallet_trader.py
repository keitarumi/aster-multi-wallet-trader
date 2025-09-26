import warnings
warnings.filterwarnings('ignore')

import yaml
import time
import random
import hashlib
import hmac
import logging
import os
import signal
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from itertools import combinations
import requests
from colorama import init, Fore, Style
from dotenv import load_dotenv
import json
try:
    from database_manager import DatabaseManager
except ImportError:
    # When imported from outside src directory
    from src.database_manager import DatabaseManager

init(autoreset=True)
load_dotenv()


class DiscordNotifier:
    """Discord notification handler"""

    def __init__(self, webhook_url: str, config: dict):
        self.webhook_url = webhook_url
        self.config = config

    def send_embed(self, embed: dict):
        """Send embed to Discord"""
        try:
            response = requests.post(
                self.webhook_url,
                json={"embeds": [embed]},
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()
        except Exception as e:
            logging.error(f"Failed to send Discord notification: {e}")

    def send_position_open_notification(self, symbol: str, wallet_long: str, wallet_short: str, quantity: float, hold_time: float):
        """Send notification when position is opened"""
        embed = {
            "title": "📈 Position Opened",
            "color": 0x00ff00,
            "fields": [
                {"name": "Symbol", "value": symbol, "inline": True},
                {"name": "Quantity", "value": str(quantity), "inline": True},
                {"name": "Hold Time", "value": f"{hold_time:.1f} min", "inline": True},
                {"name": "Long Position", "value": wallet_long, "inline": True},
                {"name": "Short Position", "value": wallet_short, "inline": True}
            ],
            "timestamp": datetime.now().isoformat(),
            "footer": {"text": "Aster Multi-Wallet Trader"}
        }
        self.send_embed(embed)

    def send_balance_report(self, wallets):
        """Send balance report to Discord"""
        if not self.webhook_url:
            return

        fields = []
        total_balance = 0

        for wallet_id, wallet in wallets.items():
            balance = wallet.get_account_balance()
            if balance is not None:
                total_balance += balance
                emoji = "🟢" if balance >= 100 else "🔴"
                fields.append({
                    "name": wallet.name,
                    "value": f"{emoji} ${balance:.2f} USDT",
                    "inline": True
                })

        embed = {
            "title": "💰 Wallet Balance Report",
            "color": 0x00ff00 if total_balance >= len(wallets) * 100 else 0xff0000,
            "fields": fields,
            "footer": {
                "text": f"Total: ${total_balance:.2f} USDT | Wallets: {len(wallets)}",
                "icon_url": "https://cdn.discordapp.com/embed/avatars/0.png"
            },
            "timestamp": datetime.now().isoformat()
        }

        self.send_embed(embed)
        logging.info(f"Balance report sent to Discord (Total: ${total_balance:.2f})")

    def send_position_close_notification(self, symbol: str, positions: list, wallets: dict):
        """Send notification when position is closed"""
        embed = {
            "title": "📉 Position Closed",
            "color": 0xffaa00,
            "fields": [
                {"name": "Symbol", "value": symbol, "inline": True},
                {"name": "Closed Positions", "value": f"{len(positions)} positions", "inline": True}
            ],
            "timestamp": datetime.now().isoformat(),
            "footer": {"text": "Aster Multi-Wallet Trader"}
        }

        for pos in positions:
            wallet_name = wallets.get(pos['wallet'], pos['wallet'])
            embed['fields'].append({
                "name": wallet_name,
                "value": f"{pos['side']} {pos['quantity']}",
                "inline": True
            })

        self.send_embed(embed)

class WalletManager:
    def __init__(self, wallet_id: str, api_settings: dict):
        env_prefix = wallet_id.upper()
        self.api_key = os.getenv(f"{env_prefix}_API_KEY")
        self.api_secret = os.getenv(f"{env_prefix}_API_SECRET")

        if not self.api_key or not self.api_secret:
            raise ValueError(f"API credentials not found for {wallet_id}. Please check your .env file.")

        # Generate wallet name from ID (e.g., WALLET_A -> Wallet A)
        self.name = wallet_id.replace('_', ' ').title()
        self.wallet_id = wallet_id
        self.base_url = api_settings['base_url']
        self.timeout = api_settings['timeout']
        self.session = requests.Session()

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
        """Make API request with retry logic"""
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
                response = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
            elif method == 'POST':
                response = self.session.post(url, params=params, headers=headers, timeout=self.timeout)
            else:
                raise ValueError(f"Unsupported method: {method}")

            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"API request failed for {self.name}: {e}")
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

    def get_position(self, symbol: str) -> Optional[dict]:
        """Get position information for a symbol"""
        params = {'symbol': symbol}
        result = self._make_request('GET', '/fapi/v2/positionRisk', params, signed=True)
        if result:
            for pos in result:
                if pos['symbol'] == symbol:
                    return pos
        return None


class MultiWalletTrader:
    def __init__(self, config_path: str):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        self.setup_logging()
        self.wallets = self._auto_detect_wallets()
        self.symbols = self.config['trading_params']['symbols']
        self.active_positions = {}
        self.position_timers = {}
        self.round_counter = 0
        self.discord_notifier = self._setup_discord()
        self.db_manager = DatabaseManager()  # Initialize database manager
        self.shutdown_flag = False  # Flag for graceful shutdown
        self.last_report_time = datetime.now()  # Track last report time

        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, sig, frame):
        """Handle shutdown signals gracefully"""
        if self.shutdown_flag:
            logging.info(f"{Fore.RED}Force shutdown requested. Exiting immediately.{Style.RESET_ALL}")
            sys.exit(1)

        logging.info(f"\n{Fore.YELLOW}Shutdown signal received. Closing positions...{Style.RESET_ALL}")
        logging.info(f"{Fore.YELLOW}Press Ctrl+C again to force shutdown.{Style.RESET_ALL}")
        self.shutdown_flag = True

    def setup_logging(self):
        """Setup logging configuration"""
        os.makedirs('logs', exist_ok=True)
        logging.basicConfig(
            level=getattr(logging, self.config['logging']['log_level']),
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.config['logging']['log_file']),
                logging.StreamHandler()
            ]
        )

    def _auto_detect_wallets(self) -> Dict[str, WalletManager]:
        """Auto-detect and initialize wallets from environment variables"""
        wallets = {}
        wallet_pattern = r'^WALLET_([A-Z]+)_API_KEY$'

        # Find all wallet IDs from environment variables
        detected_wallet_ids = set()
        for env_key in os.environ.keys():
            import re
            match = re.match(wallet_pattern, env_key)
            if match:
                wallet_letter = match.group(1)
                wallet_id = f"WALLET_{wallet_letter}"
                detected_wallet_ids.add(wallet_id)

        # Sort wallet IDs for consistent ordering
        detected_wallet_ids = sorted(detected_wallet_ids)

        if not detected_wallet_ids:
            logging.error("No wallets detected in .env file!")
            logging.error("Please add wallet credentials in the format:")
            logging.error("WALLET_A_API_KEY=xxx")
            logging.error("WALLET_A_API_SECRET=xxx")
            raise ValueError("No wallets found in environment variables")

        # Initialize detected wallets and check balances
        valid_wallets = {}
        for wallet_id in detected_wallet_ids:
            try:
                wallet = WalletManager(wallet_id, self.config['api_settings'])
                balance = wallet.get_account_balance()

                if balance is not None and balance >= 10:  # Minimum balance requirement
                    valid_wallets[wallet_id.lower()] = wallet
                    logging.info(f"✅ {wallet_id}: ${balance:.2f} USDT")
                elif balance is not None:
                    logging.warning(f"⚠️  {wallet_id}: Insufficient balance ${balance:.2f} USDT (min: $10)")
                else:
                    logging.warning(f"⚠️  {wallet_id}: Failed to check balance")

            except ValueError as e:
                logging.warning(f"⚠️  {wallet_id}: {e}")
                continue

        if len(valid_wallets) < 2:
            raise ValueError(f"At least 2 wallets with sufficient balance are required. Found: {len(valid_wallets)}")

        logging.info(f"\n📊 Active wallets: {len(valid_wallets)}")

        return valid_wallets

    def _setup_discord(self) -> Optional[object]:
        """Setup Discord notifications if webhook URL is available"""
        webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
        if webhook_url:
            logging.info("📢 Discord notifications enabled")
            return DiscordNotifier(webhook_url, self.config.get('discord', {}))
        else:
            logging.info("🔕 Discord notifications disabled (no webhook URL)")
            return None

    def get_available_wallets(self) -> List[str]:
        """Get wallets that don't have active positions"""
        available_wallets = []
        for wallet_id, wallet in self.wallets.items():
            if wallet_id not in [pos['wallet'] for positions in self.active_positions.values() for pos in positions]:
                available_wallets.append(wallet_id)
        return available_wallets

    def get_available_pairs(self) -> List[Tuple[str, str]]:
        """Get wallet pairs that don't have active positions (legacy method)"""
        available_wallets = self.get_available_wallets()
        if len(available_wallets) < 2:
            return []
        return list(combinations(available_wallets, 2))

    def split_wallets_into_teams(self, wallets: List[str]) -> Tuple[List[str], List[str]]:
        """Split wallets into long and short teams"""
        wallet_count = len(wallets)

        if wallet_count < 2:
            raise ValueError("Need at least 2 wallets for team trading")

        # Randomly shuffle wallets
        shuffled_wallets = wallets.copy()
        random.shuffle(shuffled_wallets)

        # Determine team sizes (at least 1 wallet per team)
        # Possible splits: 1:1, 1:2, 2:2, 1:3, 2:3, etc.
        max_team_size = wallet_count - 1
        long_team_size = random.randint(1, max_team_size)
        short_team_size = wallet_count - long_team_size

        # Split into teams
        long_team = shuffled_wallets[:long_team_size]
        short_team = shuffled_wallets[long_team_size:]

        logging.info(f"Team allocation - Long: {len(long_team)} wallets, Short: {len(short_team)} wallets")
        logging.debug(f"Long team: {[self.wallets[w].name for w in long_team]}")
        logging.debug(f"Short team: {[self.wallets[w].name for w in short_team]}")

        return long_team, short_team

    def distribute_quantity_in_teams(self, total_quantity: float, team_size: int, symbol: str) -> List[float]:
        """Distribute quantity randomly among team members with minimum constraints"""
        if team_size == 1:
            return [total_quantity]

        # Get current price and minimum order size
        price = self._get_current_price(symbol)
        if not price:
            logging.error(f"Cannot get price for {symbol}")
            return [total_quantity]  # Fallback to single allocation

        # Calculate minimum quantity based on minimum USDT order size
        min_order_usdt = self.config['trading_params'].get('minimum_order_size_usdt', 5)
        min_quantity_from_usdt = min_order_usdt / price

        # Set minimum quantity based on symbol precision
        if 'BTC' in symbol or 'ETH' in symbol:
            min_step = 0.001
            decimals = 3
        elif 'SOL' in symbol or 'ASTER' in symbol:
            min_step = 0.01
            decimals = 2
        else:
            min_step = 0.001
            decimals = 3

        # Use the larger of the two minimums
        min_quantity = max(min_quantity_from_usdt, min_step)
        min_quantity = round(min_quantity + min_step, decimals)  # Add buffer

        # Check if we can distribute to all team members
        required_min_total = min_quantity * team_size
        if total_quantity < required_min_total:
            logging.warning(f"Total quantity {total_quantity} is less than required minimum {required_min_total} for {team_size} wallets")
            # Reduce team size or return single allocation
            max_team_size = int(total_quantity / min_quantity)
            if max_team_size <= 1:
                return [total_quantity]
            else:
                logging.info(f"Reducing team size from {team_size} to {max_team_size}")
                team_size = max_team_size

        # Allocate minimum to each wallet first
        quantities = [min_quantity] * team_size
        remaining = total_quantity - (min_quantity * team_size)

        if remaining <= 0:
            # If no remaining after minimum allocation, adjust last wallet
            quantities[-1] = total_quantity - sum(quantities[:-1])
            return [round(q, decimals) for q in quantities]

        # Distribute remaining randomly
        random_proportions = [random.random() for _ in range(team_size)]
        total_proportion = sum(random_proportions)
        normalized = [p / total_proportion for p in random_proportions]

        for i in range(team_size):
            additional = remaining * normalized[i]
            quantities[i] += additional

        # Apply rounding
        quantities = [round(q, decimals) for q in quantities]

        # Adjust last quantity to ensure exact total
        actual_total = sum(quantities[:-1])
        quantities[-1] = round(total_quantity - actual_total, decimals)

        # Final validation
        for i, qty in enumerate(quantities):
            if qty < min_quantity:
                logging.warning(f"Quantity {qty} is below minimum {min_quantity}, adjusting...")
                quantities[i] = min_quantity

        # Log distribution info
        logging.debug(f"Distributed {total_quantity} {symbol} to {team_size} wallets:")
        logging.debug(f"  Min quantity: {min_quantity} ({min_order_usdt} USDT @ ${price:.2f})")
        logging.debug(f"  Distribution: {quantities}")
        logging.debug(f"  Total: {sum(quantities):.{decimals}f}")

        return quantities

    def get_available_symbols(self) -> List[str]:
        """Get symbols that aren't currently being traded"""
        return [s for s in self.symbols if s not in self.active_positions]

    def calculate_position_size(self, symbol: str) -> float:
        """Calculate position size with variance"""
        # Check for symbol-specific position size first
        position_sizes = self.config['trading_params'].get('position_sizes', {})

        if symbol in position_sizes:
            base_size = position_sizes[symbol]
            logging.debug(f"Using symbol-specific size for {symbol}: ${base_size} USDT")
        else:
            # Fall back to default position size
            base_size = self.config['trading_params'].get('default_position_size_usdt',
                                                           self.config['trading_params'].get('base_position_size_usdt', 100))
            logging.debug(f"Using default size for {symbol}: ${base_size} USDT")

        variance = self.config['trading_params']['position_size_variance']

        price = self._get_current_price(symbol)
        if not price:
            return 0

        size_usdt = base_size * (1 + random.uniform(-variance, variance))

        # Adjust precision based on symbol and exchange requirements
        if 'BTC' in symbol or 'ETH' in symbol:
            # BTCUSDT and ETHUSDT require 0.001 step size (3 decimals)
            raw_quantity = size_usdt / price
            quantity = round(raw_quantity, 3)
        elif 'SOL' in symbol or 'ASTER' in symbol:
            # SOLUSDT and ASTERUSDT require 0.01 step size (2 decimals)
            raw_quantity = size_usdt / price
            quantity = round(raw_quantity, 2)
        else:
            # Default to 3 decimals for unknown symbols
            raw_quantity = size_usdt / price
            quantity = round(raw_quantity, 3)

        logging.debug(f"Position sizing for {symbol}: ${size_usdt:.2f} / ${price:.2f} = {quantity}")
        return quantity

    def _get_current_price(self, symbol: str) -> Optional[float]:
        """Get current market price"""
        url = f"{self.config['api_settings']['base_url']}/fapi/v1/ticker/price"
        try:
            response = requests.get(url, params={'symbol': symbol}, timeout=10)
            response.raise_for_status()
            return float(response.json()['price'])
        except Exception as e:
            logging.error(f"Failed to get price for {symbol}: {e}")
            return None

    def open_team_hedge_position(self, symbol: str):
        """Open hedge positions using team-based allocation"""
        available_wallets = self.get_available_wallets()

        if len(available_wallets) < 2:
            logging.warning("Not enough available wallets for team trading")
            return False

        # Calculate total position size first
        total_quantity = self.calculate_position_size(symbol)
        if total_quantity == 0:
            logging.error(f"Failed to calculate position size for {symbol}")
            return False

        # Get price and check minimum requirements
        price = self._get_current_price(symbol)
        if not price:
            logging.error(f"Failed to get price for {symbol}")
            return False

        # Check if total position meets minimum for at least 2 wallets
        min_order_usdt = self.config['trading_params'].get('minimum_order_size_usdt', 5)
        min_quantity_per_wallet = min_order_usdt / price

        if total_quantity < (min_quantity_per_wallet * 2):
            logging.warning(f"Total quantity {total_quantity} {symbol} (${total_quantity * price:.2f}) is too small for team trading")
            logging.warning(f"Minimum required: {min_quantity_per_wallet * 2:.4f} {symbol} (${min_order_usdt * 2:.2f})")
            return False

        # Split wallets into teams
        long_team, short_team = self.split_wallets_into_teams(available_wallets)

        # Distribute quantities within teams
        long_quantities = self.distribute_quantity_in_teams(total_quantity, len(long_team), symbol)
        short_quantities = self.distribute_quantity_in_teams(total_quantity, len(short_team), symbol)

        # Get current price for recording
        price = self._get_current_price(symbol)
        if not price:
            logging.error(f"Failed to get price for {symbol}")
            return False

        # Get execution delay from config
        execution_delay = self.config['trading_params'].get('wallet_execution_delay', 1)

        # Track all positions for this symbol
        symbol_positions = []
        trade_ids = []
        failed = False

        # Open LONG positions
        logging.info(f"{Fore.GREEN}Opening LONG positions:{Style.RESET_ALL}")
        for i, (wallet_id, quantity) in enumerate(zip(long_team, long_quantities)):
            wallet = self.wallets[wallet_id]
            logging.info(f"  {wallet.name}: {quantity} {symbol}")

            order = wallet.place_order(symbol, 'BUY', quantity)
            if not order:
                logging.error(f"Failed to open LONG position for {wallet.name}")
                failed = True
                break

            # Record trade
            trade_id = self.db_manager.record_trade({
                'symbol': symbol,
                'wallet_id': wallet_id,
                'wallet_name': wallet.name,
                'side': 'BUY',
                'quantity': quantity,
                'price': price,
                'usdt_value': quantity * price,
                'order_id': order.get('orderId', '') if isinstance(order, dict) else '',
                'status': 'SUCCESS'
            })
            trade_ids.append(trade_id)

            symbol_positions.append({
                'wallet': wallet_id,
                'side': 'BUY',
                'quantity': quantity,
                'team': 'LONG'
            })

            if i < len(long_team) - 1:
                time.sleep(execution_delay)

        # Wait before opening SHORT positions
        if not failed:
            logging.info(f"Waiting {execution_delay}s before opening SHORT positions...")
            time.sleep(execution_delay)

            # Open SHORT positions
            logging.info(f"{Fore.RED}Opening SHORT positions:{Style.RESET_ALL}")
            for i, (wallet_id, quantity) in enumerate(zip(short_team, short_quantities)):
                wallet = self.wallets[wallet_id]
                logging.info(f"  {wallet.name}: {quantity} {symbol}")

                order = wallet.place_order(symbol, 'SELL', quantity)
                if not order:
                    logging.error(f"Failed to open SHORT position for {wallet.name}")
                    failed = True
                    break

                # Record trade
                trade_id = self.db_manager.record_trade({
                    'symbol': symbol,
                    'wallet_id': wallet_id,
                    'wallet_name': wallet.name,
                    'side': 'SELL',
                    'quantity': quantity,
                    'price': price,
                    'usdt_value': quantity * price,
                    'order_id': order.get('orderId', '') if isinstance(order, dict) else '',
                    'status': 'SUCCESS'
                })
                trade_ids.append(trade_id)

                symbol_positions.append({
                    'wallet': wallet_id,
                    'side': 'SELL',
                    'quantity': quantity,
                    'team': 'SHORT'
                })

                if i < len(short_team) - 1:
                    time.sleep(execution_delay)

        # If any position failed, close all opened positions
        if failed:
            logging.error("Failed to open all positions, rolling back...")
            for pos in symbol_positions:
                wallet = self.wallets[pos['wallet']]
                wallet.close_position(symbol, pos['side'], pos['quantity'])
            return False

        # Calculate hold time
        hold_time = random.uniform(
            self.config['trading_params']['min_hold_time_minutes'],
            self.config['trading_params']['max_hold_time_minutes']
        )

        # Create position record in database
        long_team_names = ', '.join([self.wallets[w].name for w in long_team])
        short_team_names = ', '.join([self.wallets[w].name for w in short_team])

        position_id = self.db_manager.create_position({
            'symbol': symbol,
            'wallet_long': long_team_names,
            'wallet_short': short_team_names,
            'quantity': total_quantity,
            'open_time': datetime.now(),
            'hold_minutes': hold_time
        })

        # Link trades to position
        if position_id:
            for trade_id in trade_ids:
                if trade_id:
                    self.db_manager.link_trade_to_position(position_id, trade_id, 'OPEN')

        # Store position info with position_id
        for pos in symbol_positions:
            pos['position_id'] = position_id

        self.active_positions[symbol] = symbol_positions
        self.position_timers[symbol] = {
            'open_time': datetime.now(),
            'close_time': datetime.now() + timedelta(minutes=hold_time),
            'hold_minutes': hold_time
        }

        # Log summary
        logging.info(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
        logging.info(f"{Fore.GREEN}Team hedge position opened:{Style.RESET_ALL}")
        logging.info(f"  Symbol: {symbol}")
        logging.info(f"  Total quantity: {total_quantity}")
        logging.info(f"  Long team ({len(long_team)}): {long_quantities}")
        logging.info(f"  Short team ({len(short_team)}): {short_quantities}")
        logging.info(f"  Hold time: {hold_time:.1f} minutes")
        logging.info(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}")

        # Send Discord notification
        if self.discord_notifier and self.config.get('discord', {}).get('send_on_position_open', False):
            self.discord_notifier.send_position_open_notification(
                symbol=symbol,
                wallet_long=long_team_names,
                wallet_short=short_team_names,
                quantity=total_quantity,
                hold_time=hold_time
            )

        return True

    def open_hedge_position(self, wallet_pair: Tuple[str, str], symbol: str):
        """Open hedge positions for a wallet pair"""
        wallet_a_id, wallet_b_id = wallet_pair
        wallet_a = self.wallets[wallet_a_id]
        wallet_b = self.wallets[wallet_b_id]

        quantity = self.calculate_position_size(symbol)
        if quantity == 0:
            logging.error(f"Failed to calculate position size for {symbol}")
            return False

        # Get current price for recording
        price = self._get_current_price(symbol)
        usdt_value = quantity * price if price else 0

        # Get execution delay from config
        execution_delay = self.config['trading_params'].get('wallet_execution_delay', 1)

        # Open first position (LONG)
        logging.info(f"Opening LONG position on {wallet_a.name}...")
        order_a = wallet_a.place_order(symbol, 'BUY', quantity)
        if not order_a:
            logging.error(f"Failed to open LONG position for {wallet_a.name}")
            return False

        # Record first trade in database
        trade_id_a = self.db_manager.record_trade({
            'symbol': symbol,
            'wallet_id': wallet_a_id,
            'wallet_name': wallet_a.name,
            'side': 'BUY',
            'quantity': quantity,
            'price': price,
            'usdt_value': usdt_value,
            'order_id': order_a.get('orderId', '') if isinstance(order_a, dict) else '',
            'status': 'SUCCESS'
        })

        # Wait configured delay before opening opposite position
        logging.info(f"Waiting {execution_delay}s before opening opposite position...")
        time.sleep(execution_delay)

        # Open second position (SHORT)
        logging.info(f"Opening SHORT position on {wallet_b.name}...")
        order_b = wallet_b.place_order(symbol, 'SELL', quantity)
        if not order_b:
            logging.error(f"Failed to open SHORT position for {wallet_b.name}")
            wallet_a.close_position(symbol, 'BUY', quantity)
            return False

        # Record second trade in database
        trade_id_b = self.db_manager.record_trade({
            'symbol': symbol,
            'wallet_id': wallet_b_id,
            'wallet_name': wallet_b.name,
            'side': 'SELL',
            'quantity': quantity,
            'price': price,
            'usdt_value': usdt_value,
            'order_id': order_b.get('orderId', '') if isinstance(order_b, dict) else '',
            'status': 'SUCCESS'
        })

        hold_time = random.uniform(
            self.config['trading_params']['min_hold_time_minutes'],
            self.config['trading_params']['max_hold_time_minutes']
        )

        # Create position record in database
        position_id = self.db_manager.create_position({
            'symbol': symbol,
            'wallet_long': wallet_a.name,
            'wallet_short': wallet_b.name,
            'quantity': quantity,
            'open_time': datetime.now(),
            'hold_minutes': hold_time
        })

        # Link trades to position
        if position_id and trade_id_a and trade_id_b:
            self.db_manager.link_trade_to_position(position_id, trade_id_a, 'OPEN')
            self.db_manager.link_trade_to_position(position_id, trade_id_b, 'OPEN')

        self.active_positions[symbol] = [
            {'wallet': wallet_a_id, 'side': 'BUY', 'quantity': quantity, 'position_id': position_id},
            {'wallet': wallet_b_id, 'side': 'SELL', 'quantity': quantity}
        ]
        self.position_timers[symbol] = {
            'open_time': datetime.now(),
            'close_time': datetime.now() + timedelta(minutes=hold_time),
            'hold_minutes': hold_time
        }

        logging.info(f"{Fore.GREEN}Opened hedge position:{Style.RESET_ALL}")
        logging.info(f"  Symbol: {symbol}")
        logging.info(f"  {wallet_a.name}: LONG {quantity}")
        logging.info(f"  {wallet_b.name}: SHORT {quantity}")
        logging.info(f"  Hold time: {hold_time:.1f} minutes")

        # Send Discord notification for position open
        if self.discord_notifier and self.config.get('discord', {}).get('send_on_position_open', False):
            self.discord_notifier.send_position_open_notification(
                symbol=symbol,
                wallet_long=wallet_a.name,
                wallet_short=wallet_b.name,
                quantity=quantity,
                hold_time=hold_time
            )

        return True

    def close_hedge_position(self, symbol: str):
        """Close hedge positions"""
        if symbol not in self.active_positions:
            return False

        positions = self.active_positions[symbol]
        success = True
        close_trade_ids = []

        # Get current price for recording
        price = self._get_current_price(symbol)

        # Get position_id if it exists
        position_id = positions[0].get('position_id') if positions else None

        # Get execution delay from config
        execution_delay = self.config['trading_params'].get('wallet_execution_delay', 1)

        for i, pos in enumerate(positions):
            wallet = self.wallets[pos['wallet']]

            # Add delay between closing positions (except for the first one)
            if i > 0:
                logging.info(f"Waiting {execution_delay}s before closing next position...")
                time.sleep(execution_delay)

            logging.info(f"Closing position on {wallet.name}...")
            order = wallet.close_position(symbol, pos['side'], pos['quantity'])
            if not order:
                logging.error(f"Failed to close position for {wallet.name}")
                success = False
            else:
                logging.info(f"{Fore.YELLOW}Closed position:{Style.RESET_ALL} {wallet.name} - {symbol}")

                # Record closing trade in database
                close_side = 'SELL' if pos['side'] == 'BUY' else 'BUY'
                trade_id = self.db_manager.record_trade({
                    'symbol': symbol,
                    'wallet_id': pos['wallet'],
                    'wallet_name': wallet.name,
                    'side': close_side,
                    'quantity': pos['quantity'],
                    'price': price,
                    'usdt_value': pos['quantity'] * price if price else 0,
                    'order_id': order.get('orderId', '') if isinstance(order, dict) else '',
                    'status': 'SUCCESS'
                })

                if trade_id:
                    close_trade_ids.append(trade_id)
                    # Link closing trade to position
                    if position_id:
                        self.db_manager.link_trade_to_position(position_id, trade_id, 'CLOSE')

        if success:
            # Close position in database
            if position_id:
                self.db_manager.close_position(position_id)

            # Send Discord notification for position close
            if self.discord_notifier and self.config.get('discord', {}).get('send_on_position_close', False):
                self.discord_notifier.send_position_close_notification(
                    symbol=symbol,
                    positions=positions,
                    wallets={pos['wallet']: self.wallets[pos['wallet']].name for pos in positions}
                )

            del self.active_positions[symbol]
            del self.position_timers[symbol]

        return success

    def check_positions_for_closing(self):
        """Check and close positions that have reached their hold time"""
        current_time = datetime.now()
        symbols_to_close = []

        for symbol, timer in self.position_timers.items():
            if current_time >= timer['close_time']:
                symbols_to_close.append(symbol)

        for symbol in symbols_to_close:
            logging.info(f"Position hold time reached for {symbol}")
            self.close_hedge_position(symbol)

    def execute_trading_round(self):
        """Execute one complete trading round using team-based allocation"""
        self.round_counter += 1
        logging.info(f"\n{Fore.CYAN}=== Trading Round {self.round_counter} ==={Style.RESET_ALL}")

        available_wallets = self.get_available_wallets()
        available_symbols = self.get_available_symbols()

        if len(available_wallets) < 2 or not available_symbols:
            logging.info("Not enough available wallets or no available symbols for new positions")
            return

        symbol = random.choice(available_symbols)

        # Use team-based trading
        self.open_team_hedge_position(symbol)

    def check_and_send_balance_report(self):
        """Check if it's time to send a balance report"""
        if not self.discord_notifier:
            return

        # Get report interval from config (default 60 minutes)
        report_interval_minutes = self.config.get('discord', {}).get('report_interval_minutes', 60)

        # Check if enough time has passed
        time_since_last_report = (datetime.now() - self.last_report_time).total_seconds() / 60

        if time_since_last_report >= report_interval_minutes:
            logging.info(f"Sending scheduled balance report (interval: {report_interval_minutes} minutes)")
            self.discord_notifier.send_balance_report(self.wallets)
            self.last_report_time = datetime.now()

    def run(self):
        """Main trading loop"""
        logging.info(f"{Fore.MAGENTA}Starting Multi-Wallet Hedge Trading System{Style.RESET_ALL}")
        logging.info(f"Wallets: {len(self.wallets)}")
        logging.info(f"Symbols: {', '.join(self.symbols)}")

        # Log parallel trading mode status
        parallel_mode = self.config['trading_params'].get('parallel_trading_enabled', False)
        logging.info(f"Parallel trading: {Fore.GREEN + 'ENABLED' if parallel_mode else Fore.YELLOW + 'DISABLED'}{Style.RESET_ALL}")

        # Send initial balance report
        if self.discord_notifier:
            logging.info("Sending initial balance report...")
            self.discord_notifier.send_balance_report(self.wallets)

        try:
            while not self.shutdown_flag:
                self.check_positions_for_closing()

                # Check if it's time to send balance report
                self.check_and_send_balance_report()

                # Check for shutdown before opening new positions
                if self.shutdown_flag:
                    break

                if parallel_mode:
                    # Parallel mode: can open new positions even with active ones
                    available_pairs = self.get_available_pairs()
                    available_symbols = self.get_available_symbols()

                    if available_pairs and available_symbols:
                        logging.info(f"{Fore.BLUE}Starting new position (parallel mode)...{Style.RESET_ALL}")
                        self.execute_trading_round()
                    else:
                        logging.info(f"Active positions: {list(self.active_positions.keys())}")
                        logging.info(f"Available pairs: {len(available_pairs)}, Available symbols: {len(available_symbols)}")
                        time.sleep(30)
                else:
                    # Sequential mode: wait for all positions to close
                    if not self.active_positions:
                        # Apply cooldown between rounds
                        cooldown_time = random.uniform(
                            self.config['trading_params'].get('min_cooldown_between_rounds_seconds', 120),
                            self.config['trading_params'].get('max_cooldown_between_rounds_seconds', 300)
                        )
                        logging.info(f"{Fore.BLUE}All positions closed. Cooldown for {cooldown_time:.0f} seconds...{Style.RESET_ALL}")

                        # Check for shutdown during cooldown
                        for _ in range(int(cooldown_time)):
                            if self.shutdown_flag:
                                break
                            time.sleep(1)

                        if not self.shutdown_flag:
                            logging.info(f"{Fore.BLUE}Starting new trading round...{Style.RESET_ALL}")
                            self.execute_trading_round()
                    else:
                        logging.info(f"Active positions: {list(self.active_positions.keys())}")
                        time.sleep(30)

            # Graceful shutdown
            logging.info(f"{Fore.RED}Performing graceful shutdown...{Style.RESET_ALL}")
            self.close_all_positions()
            self.db_manager.close()
            logging.info(f"{Fore.GREEN}Shutdown complete.{Style.RESET_ALL}")

        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            self.close_all_positions()
            self.db_manager.close()  # Close database connection

    def close_all_positions(self):
        """Emergency close all positions"""
        if not self.active_positions:
            logging.info("No active positions to close.")
            return

        logging.info(f"{Fore.YELLOW}Closing {len(self.active_positions)} open positions...{Style.RESET_ALL}")

        for i, symbol in enumerate(list(self.active_positions.keys()), 1):
            logging.info(f"[{i}/{len(self.active_positions)}] Closing {symbol}...")
            self.close_hedge_position(symbol)

        logging.info(f"{Fore.GREEN}All positions closed successfully.{Style.RESET_ALL}")


if __name__ == "__main__":
    trader = MultiWalletTrader("config.yaml")
    trader.run()