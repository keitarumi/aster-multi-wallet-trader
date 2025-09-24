import os
import sys
from dotenv import load_dotenv
import requests
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()


def test_webhook_connection():
    """Test basic Discord webhook connection"""
    webhook_url = os.getenv('DISCORD_WEBHOOK_URL')

    if not webhook_url:
        print("❌ DISCORD_WEBHOOK_URL not found in .env file")
        print("\nPlease add to .env:")
        print("DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN")
        return False

    print(f"✅ Webhook URL found")
    print(f"   URL: {webhook_url[:50]}...")

    # Test with simple message
    test_data = {
        "content": f"🧪 **Test Message** - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nWebhook connection successful!"
    }

    try:
        response = requests.post(webhook_url, json=test_data)
        if response.status_code == 204:
            print("✅ Test message sent successfully!")
            return True
        else:
            print(f"❌ Failed to send message: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False


def test_embed_message():
    """Test Discord embed message"""
    webhook_url = os.getenv('DISCORD_WEBHOOK_URL')

    if not webhook_url:
        print("❌ DISCORD_WEBHOOK_URL not found")
        return False

    embed_data = {
        "embeds": [{
            "title": "🚀 Aster Wallet Test Report",
            "description": "Testing Discord webhook integration",
            "color": 0x00ff00,
            "fields": [
                {
                    "name": "💰 Test Balance",
                    "value": "**Wallet A**: $1000.00 USDT\n**Wallet B**: $1000.00 USDT",
                    "inline": False
                },
                {
                    "name": "📊 Status",
                    "value": "All systems operational",
                    "inline": True
                },
                {
                    "name": "🔌 Active Wallets",
                    "value": "2",
                    "inline": True
                }
            ],
            "footer": {
                "text": "Aster Multi-Wallet Trader Test"
            },
            "timestamp": datetime.now().isoformat()
        }]
    }

    try:
        response = requests.post(webhook_url, json=embed_data)
        if response.status_code == 204:
            print("✅ Embed message sent successfully!")
            return True
        else:
            print(f"❌ Failed to send embed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_reporter():
    """Test the actual Discord reporter"""
    try:
        from discord_reporter import DiscordReporter

        print("\n📊 Testing Discord Reporter...")
        reporter = DiscordReporter("config.yaml")

        # Check wallet detection
        print(f"\n🔍 Detected wallets: {len(reporter.wallets)}")
        for wallet_id in reporter.wallets.keys():
            print(f"   - {wallet_id}")

        # Send test report
        print("\n📧 Sending balance report...")
        reporter.send_balance_report()

        print("\n✅ Reporter test completed!")
        return True

    except Exception as e:
        print(f"\n❌ Reporter test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Discord Webhook Test")
    print("=" * 60)

    # Test 1: Basic connection
    print("\n1. Testing webhook connection...")
    if test_webhook_connection():
        print("   ✅ Connection test passed")
    else:
        print("   ❌ Connection test failed")
        exit(1)

    # Test 2: Embed message
    print("\n2. Testing embed message...")
    if test_embed_message():
        print("   ✅ Embed test passed")
    else:
        print("   ❌ Embed test failed")

    # Test 3: Full reporter
    print("\n3. Testing full reporter...")
    if test_reporter():
        print("   ✅ Reporter test passed")
    else:
        print("   ❌ Reporter test failed")

    print("\n" + "=" * 60)
    print("✅ All tests completed! Check your Discord channel.")
    print("=" * 60)