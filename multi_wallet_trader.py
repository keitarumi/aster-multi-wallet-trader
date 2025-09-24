import warnings
warnings.filterwarnings('ignore')

import yaml
import time
import random
import hashlib
import hmac
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from itertools import combinations
import requests
from colorama import init, Fore, Style
from dotenv import load_dotenv

init(autoreset=True)
load_dotenv()

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

    def get_available_pairs(self) -> List[Tuple[str, str]]:
        """Get wallet pairs that don't have active positions"""
        available_wallets = []
        for wallet_id, wallet in self.wallets.items():
            if wallet_id not in [pos['wallet'] for positions in self.active_positions.values() for pos in positions]:
                available_wallets.append(wallet_id)

        if len(available_wallets) < 2:
            return []

        return list(combinations(available_wallets, 2))

    def get_available_symbols(self) -> List[str]:
        """Get symbols that aren't currently being traded"""
        return [s for s in self.symbols if s not in self.active_positions]

    def calculate_position_size(self, symbol: str) -> float:
        """Calculate position size with variance"""
        base_size = self.config['trading_params']['base_position_size_usdt']
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

    def open_hedge_position(self, wallet_pair: Tuple[str, str], symbol: str):
        """Open hedge positions for a wallet pair"""
        wallet_a_id, wallet_b_id = wallet_pair
        wallet_a = self.wallets[wallet_a_id]
        wallet_b = self.wallets[wallet_b_id]

        quantity = self.calculate_position_size(symbol)
        if quantity == 0:
            logging.error(f"Failed to calculate position size for {symbol}")
            return False

        # Get execution delay from config
        execution_delay = self.config['trading_params'].get('wallet_execution_delay', 1)

        # Open first position (LONG)
        logging.info(f"Opening LONG position on {wallet_a.name}...")
        order_a = wallet_a.place_order(symbol, 'BUY', quantity)
        if not order_a:
            logging.error(f"Failed to open LONG position for {wallet_a.name}")
            return False

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

        hold_time = random.uniform(
            self.config['trading_params']['min_hold_time_minutes'],
            self.config['trading_params']['max_hold_time_minutes']
        )

        self.active_positions[symbol] = [
            {'wallet': wallet_a_id, 'side': 'BUY', 'quantity': quantity},
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

        return True

    def close_hedge_position(self, symbol: str):
        """Close hedge positions"""
        if symbol not in self.active_positions:
            return False

        positions = self.active_positions[symbol]
        success = True

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

        if success:
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
        """Execute one complete trading round"""
        self.round_counter += 1
        logging.info(f"\n{Fore.CYAN}=== Trading Round {self.round_counter} ==={Style.RESET_ALL}")

        available_pairs = self.get_available_pairs()
        available_symbols = self.get_available_symbols()

        if not available_pairs or not available_symbols:
            logging.info("No available pairs or symbols for new positions")
            return

        wallet_pair = random.choice(available_pairs)
        symbol = random.choice(available_symbols)

        self.open_hedge_position(wallet_pair, symbol)

        wait_time = random.uniform(
            self.config['trading_params']['min_wait_between_trades_seconds'],
            self.config['trading_params']['max_wait_between_trades_seconds']
        )
        logging.info(f"Waiting {wait_time:.0f} seconds before next check...")
        time.sleep(wait_time)

    def run(self):
        """Main trading loop"""
        logging.info(f"{Fore.MAGENTA}Starting Multi-Wallet Hedge Trading System{Style.RESET_ALL}")
        logging.info(f"Wallets: {len(self.wallets)}")
        logging.info(f"Symbols: {', '.join(self.symbols)}")

        try:
            while True:
                self.check_positions_for_closing()

                if not self.active_positions:
                    logging.info(f"{Fore.BLUE}All positions closed. Starting new round...{Style.RESET_ALL}")
                    self.execute_trading_round()
                else:
                    logging.info(f"Active positions: {list(self.active_positions.keys())}")
                    time.sleep(30)

        except KeyboardInterrupt:
            logging.info(f"\n{Fore.RED}Shutting down...{Style.RESET_ALL}")
            self.close_all_positions()
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            self.close_all_positions()

    def close_all_positions(self):
        """Emergency close all positions"""
        logging.info("Closing all open positions...")
        for symbol in list(self.active_positions.keys()):
            self.close_hedge_position(symbol)
        logging.info("All positions closed.")


if __name__ == "__main__":
    trader = MultiWalletTrader("config.yaml")
    trader.run()