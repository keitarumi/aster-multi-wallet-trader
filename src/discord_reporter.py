import warnings
warnings.filterwarnings('ignore')

import os
import yaml
import time
import hashlib
import hmac
import requests
import schedule
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dotenv import load_dotenv
import json
import re

load_dotenv()


class WalletMonitor:
    """Monitor wallet balances and positions"""

    def __init__(self, wallet_id: str):
        env_prefix = wallet_id.upper()
        self.api_key = os.getenv(f"{env_prefix}_API_KEY")
        self.api_secret = os.getenv(f"{env_prefix}_API_SECRET")
        self.wallet_id = wallet_id
        self.name = wallet_id.replace('_', ' ').title()
        self.base_url = "https://fapi.asterdex.com"

    def _generate_signature(self, params: dict) -> str:
        """Generate HMAC SHA256 signature"""
        if 'signature' in params:
            del params['signature']
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def _make_request(self, method: str, endpoint: str, params: dict = None, signed: bool = False) -> dict:
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
            else:
                response = requests.post(url, params=params, headers=headers, timeout=30)

            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"API error for {self.name}: {e}")
            return None

    def get_account_info(self) -> dict:
        """Get comprehensive account information"""
        result = self._make_request('GET', '/fapi/v2/account', signed=True)
        if result:
            return {
                'name': self.name,
                'wallet_id': self.wallet_id,
                'balance': self._extract_balance(result),
                'positions': self._extract_positions(result),
                'total_unrealized_pnl': float(result.get('totalUnrealizedProfit', 0)),
                'total_margin_balance': float(result.get('totalMarginBalance', 0)),
                'available_balance': float(result.get('availableBalance', 0))
            }
        return None

    def _extract_balance(self, account_data: dict) -> dict:
        """Extract balance information"""
        balances = {}
        if 'assets' in account_data:
            for asset in account_data['assets']:
                if float(asset.get('walletBalance', 0)) > 0:
                    balances[asset['asset']] = {
                        'wallet': float(asset['walletBalance']),
                        'available': float(asset['availableBalance']),
                        'unrealized_pnl': float(asset['unrealizedProfit'])
                    }
        return balances

    def _extract_positions(self, account_data: dict) -> list:
        """Extract active positions"""
        positions = []
        if 'positions' in account_data:
            for pos in account_data['positions']:
                if float(pos.get('positionAmt', 0)) != 0:
                    positions.append({
                        'symbol': pos['symbol'],
                        'side': 'LONG' if float(pos['positionAmt']) > 0 else 'SHORT',
                        'amount': abs(float(pos['positionAmt'])),
                        'entry_price': float(pos.get('entryPrice', 0)),
                        'mark_price': float(pos.get('markPrice', 0)),
                        'unrealized_pnl': float(pos.get('unrealizedProfit', 0))
                    })
        return positions


class DiscordReporter:
    """Send reports to Discord via webhook"""

    def __init__(self, config_path: str):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        self.webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
        if not self.webhook_url:
            raise ValueError("DISCORD_WEBHOOK_URL not found in .env file")

        self.wallets = self._detect_wallets()
        self.last_report_time = datetime.now()

    def _detect_wallets(self) -> Dict[str, WalletMonitor]:
        """Auto-detect wallets from environment"""
        wallets = {}
        wallet_pattern = r'^WALLET_([A-Z]+)_API_KEY$'

        for env_key in os.environ.keys():
            match = re.match(wallet_pattern, env_key)
            if match:
                wallet_letter = match.group(1)
                wallet_id = f"WALLET_{wallet_letter}"

                # Check if API secret exists
                if f"{wallet_id}_API_SECRET" in os.environ:
                    wallets[wallet_id] = WalletMonitor(wallet_id)
                    print(f"✅ Detected {wallet_id}")

        return wallets

    def send_to_discord(self, content: str = None, embeds: list = None):
        """Send message to Discord webhook"""
        data = {}

        if content:
            data['content'] = content

        if embeds:
            data['embeds'] = embeds

        try:
            response = requests.post(
                self.webhook_url,
                json=data,
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()
            print(f"✅ Discord notification sent")
        except Exception as e:
            print(f"❌ Failed to send Discord notification: {e}")

    def generate_balance_report(self) -> dict:
        """Generate comprehensive balance report"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        total_balance = 0
        wallet_reports = []
        all_positions = []
        low_balance_wallets = []

        for wallet_id, monitor in self.wallets.items():
            info = monitor.get_account_info()
            if info:
                usdt_balance = info['balance'].get('USDT', {}).get('wallet', 0)
                total_balance += usdt_balance

                # Check for low balance
                if usdt_balance < self.config['discord']['low_balance_threshold']:
                    low_balance_wallets.append(f"{info['name']}: ${usdt_balance:.2f}")

                wallet_reports.append(info)
                all_positions.extend(info['positions'])

        return {
            'timestamp': timestamp,
            'total_balance': total_balance,
            'wallet_reports': wallet_reports,
            'all_positions': all_positions,
            'low_balance_wallets': low_balance_wallets,
            'active_wallets': len(wallet_reports)
        }

    def format_discord_embed(self, report_data: dict) -> list:
        """Format report as Discord embed"""
        embeds = []

        # Main report embed
        embed = {
            "title": "📊 Aster Wallet Report",
            "description": f"Report generated at {report_data['timestamp']}",
            "color": 0x00ff00 if not report_data['low_balance_wallets'] else 0xffaa00,
            "fields": []
        }

        # Balance summary field
        balance_text = ""
        for wallet in report_data['wallet_reports']:
            usdt = wallet['balance'].get('USDT', {})
            balance_text += f"**{wallet['name']}**: ${usdt.get('wallet', 0):.2f} USDT\n"

        embed['fields'].append({
            "name": "💰 Wallet Balances",
            "value": balance_text or "No wallets found",
            "inline": False
        })

        # Total balance
        embed['fields'].append({
            "name": "💎 Total Balance",
            "value": f"**${report_data['total_balance']:.2f} USDT**",
            "inline": True
        })

        # Active wallets
        embed['fields'].append({
            "name": "🔌 Active Wallets",
            "value": f"{report_data['active_wallets']}",
            "inline": True
        })

        # Positions summary
        if report_data['all_positions']:
            position_text = ""
            for pos in report_data['all_positions'][:5]:  # Show first 5 positions
                pnl_emoji = "🟢" if pos['unrealized_pnl'] >= 0 else "🔴"
                position_text += f"{pnl_emoji} **{pos['symbol']}** {pos['side']} {pos['amount']:.4f} (PnL: ${pos['unrealized_pnl']:.2f})\n"

            embed['fields'].append({
                "name": f"📈 Active Positions ({len(report_data['all_positions'])} total)",
                "value": position_text,
                "inline": False
            })

        # Low balance warning
        if report_data['low_balance_wallets']:
            embed['fields'].append({
                "name": "⚠️ Low Balance Warning",
                "value": "\n".join(report_data['low_balance_wallets']),
                "inline": False
            })

        # Footer
        embed['footer'] = {
            "text": "Aster Multi-Wallet Trader",
            "icon_url": "https://raw.githubusercontent.com/asterdex/assets/main/logo.png"
        }

        embed['timestamp'] = datetime.now().isoformat()

        embeds.append(embed)
        return embeds

    def send_balance_report(self):
        """Send balance report to Discord"""
        print(f"\n📊 Generating balance report...")
        report_data = self.generate_balance_report()
        embeds = self.format_discord_embed(report_data)
        self.send_to_discord(embeds=embeds)
        self.last_report_time = datetime.now()

    def send_error_notification(self, error_message: str):
        """Send error notification to Discord"""
        if not self.config['discord']['send_on_error']:
            return

        embed = {
            "title": "❌ Error Notification",
            "description": error_message,
            "color": 0xff0000,
            "timestamp": datetime.now().isoformat(),
            "footer": {
                "text": "Aster Multi-Wallet Trader"
            }
        }

        self.send_to_discord(embeds=[embed])

    def send_trade_notification(self, trade_info: dict):
        """Send trade execution notification"""
        if not self.config['discord']['send_on_trade']:
            return

        embed = {
            "title": "💹 Trade Executed",
            "color": 0x0099ff,
            "fields": [
                {"name": "Symbol", "value": trade_info.get('symbol', 'N/A'), "inline": True},
                {"name": "Side", "value": trade_info.get('side', 'N/A'), "inline": True},
                {"name": "Quantity", "value": str(trade_info.get('quantity', 'N/A')), "inline": True},
                {"name": "Price", "value": f"${trade_info.get('price', 0):.2f}", "inline": True}
            ],
            "timestamp": datetime.now().isoformat(),
            "footer": {
                "text": "Aster Multi-Wallet Trader"
            }
        }

        self.send_to_discord(embeds=[embed])

    def run_scheduler(self):
        """Run scheduled reports"""
        interval = self.config['discord']['report_interval_minutes']

        # Schedule periodic reports
        schedule.every(interval).minutes.do(self.send_balance_report)

        print(f"📅 Scheduler started:")
        print(f"   - Reports every {interval} minutes")

        # Send initial report
        self.send_balance_report()

        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute


if __name__ == "__main__":
    try:
        reporter = DiscordReporter("config.yaml")

        # Test mode: send one report
        import sys
        if len(sys.argv) > 1 and sys.argv[1] == "test":
            print("📧 Sending test report...")
            reporter.send_balance_report()
        else:
            # Run scheduler
            print("🚀 Starting Discord reporter...")
            reporter.run_scheduler()

    except KeyboardInterrupt:
        print("\n👋 Discord reporter stopped")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()