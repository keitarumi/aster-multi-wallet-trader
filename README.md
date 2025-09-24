# Aster Multi-Wallet Trader

複数のウォレット間で相対トレード（両建て）を行い、Discord通知機能を備えた自動取引システム。

## 🚀 特徴

- **自動ウォレット検出**: .envファイルから複数ウォレットを自動認識
- **複雑な相対トレード**: 異なるウォレットペアで異なる銘柄を同時に両建て
- **自然な取引パターン**: ランダムな遅延とポジションサイズの変動
- **Discord通知**: 残高レポート、取引通知、エラー通知
- **リスク管理**: 残高不足ウォレットの自動除外

## 📋 必要条件

- Python 3.9以上
- Aster API アカウント（複数）
- Discord Webhook URL（オプション）

## 🔧 セットアップ

### 1. 依存関係のインストール

```bash
pip3 install -r requirements.txt
```

### 2. 環境変数の設定

`.env.example`をコピーして`.env`を作成し、APIキーを設定：

```bash
cp .env.example .env
```

`.env`ファイルの設定例：

```env
# Wallet A
WALLET_A_API_KEY=your_api_key_here
WALLET_A_API_SECRET=your_api_secret_here

# Wallet B
WALLET_B_API_KEY=your_api_key_here
WALLET_B_API_SECRET=your_api_secret_here

# Wallet C（オプション）
WALLET_C_API_KEY=your_api_key_here
WALLET_C_API_SECRET=your_api_secret_here

# Discord Webhook（オプション）
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/xxx/xxx
```

**重要**:
- 最低2つのウォレットが必要（両建てのため）
- ウォレットは必ずアルファベット順（A, B, C...）で追加
- 各ウォレットに最低$10 USDTの残高が必要

### 3. 設定ファイル（config.yaml）

```yaml
# トレーディングパラメータ
trading_params:
  # 取引対象の通貨ペア
  symbols:
    - BTCUSDT
    - ETHUSDT
    - ASTERUSDT
    - SOLUSDT

  # ポジションサイズ設定
  base_position_size_usdt: 100        # 基本ポジションサイズ（USDT）
  position_size_variance: 0.05        # ランダム変動幅（5% = 0.05）

  # ポジション保有時間（分）
  min_hold_time_minutes: 5            # 最小保有時間
  max_hold_time_minutes: 10           # 最大保有時間

  # 取引間隔（秒）
  min_wait_between_trades_seconds: 60  # 最小待機時間
  max_wait_between_trades_seconds: 180 # 最大待機時間

  # ウォレット間の実行ディレイ（秒）
  wallet_execution_delay: 1           # A→B実行時の遅延

# Discord通知設定
discord:
  report_interval_minutes: 60         # 定期レポート間隔
  send_on_trade: true                 # 取引時通知
  send_on_error: true                 # エラー時通知
  daily_summary_hour: 9               # 日次サマリー時刻（24時間形式）
  low_balance_threshold: 100          # 残高警告しきい値（USDT）
```

## 📊 使い方

### メイン機能

#### 1. ウォレット検出テスト

```bash
python3 test/test_wallet_detection.py
```

#### 2. 相対トレードの実行

```bash
python3 multi_wallet_trader.py
```

- 自動的に.envから有効なウォレットを検出
- 残高が$10以上のウォレットのみ使用
- `Ctrl+C`で安全に停止（全ポジションを自動クローズ）

#### 3. 2ウォレットテスト

```bash
python3 test/test_two_wallets.py
```

#### 4. シンプルな取引テスト

```bash
python3 test/test_simple_trade.py
```

### Discord通知

#### 1. Webhook接続テスト

```bash
python3 test/test_discord_webhook.py
```

#### 2. 単発レポート送信

```bash
python3 discord_reporter.py test
```

#### 3. 定期レポート実行

```bash
python3 discord_reporter.py
```

## 📝 トレーディングロジック

### 取引フロー

1. **ウォレットペア選択**: ポジションを持っていないウォレットからランダムに2つ選択
2. **銘柄選択**: 取引中でない銘柄をランダムに選択
3. **ポジションオープン**:
   - ウォレットA: ロングポジション
   - 1秒待機
   - ウォレットB: ショートポジション
4. **ポジション保有**: 5-10分のランダムな時間
5. **ポジションクローズ**:
   - ウォレットA: ポジションクローズ
   - 1秒待機
   - ウォレットB: ポジションクローズ
6. **待機**: 60-180秒のランダムな待機時間
7. **繰り返し**: 1に戻る

### ポジションサイズ計算

- 基本サイズ: 100 USDT
- 変動: ±5%（デフォルト）
- 精度調整:
  - BTC/ETH: 小数点3桁（0.001）
  - SOL/ASTER: 小数点2桁（0.01）

## 🔍 トラブルシューティング

### よくあるエラー

1. **署名エラー（-1022）**
   - APIキーとシークレットが正しいか確認
   - タイムスタンプが正確か確認

2. **精度エラー（-1111）**
   - 各通貨ペアの精度設定を確認
   - BTCは0.001、SOLは0.01単位

3. **残高不足**
   - 最低$10 USDTが必要
   - ウォレットの残高を確認

### ログファイル

ログは`logs/trading.log`に保存されます：

```bash
tail -f logs/trading.log
```

## ⚠️ 注意事項

1. **APIキーの管理**
   - `.env`ファイルは絶対にGitにコミットしない
   - APIキーには取引権限のみ付与（出金権限は不要）

2. **リスク管理**
   - 小額から開始
   - ポジションサイズを適切に設定
   - 残高を定期的に確認

3. **レート制限**
   - APIレート制限に注意
   - 過度な頻度での取引は避ける

## 📂 プロジェクト構成

```
asterdex/
├── multi_wallet_trader.py   # メインの取引システム
├── discord_reporter.py      # Discord通知機能
├── config.yaml             # 設定ファイル
├── .env                    # 環境変数（APIキー）
├── requirements.txt        # 依存関係
├── test/                   # テストスクリプト
│   ├── test_simple_trade.py
│   ├── test_two_wallets.py
│   ├── test_wallet_detection.py
│   └── test_discord_webhook.py
└── logs/                   # ログファイル
    └── trading.log
```

## 🔄 アップデート

最新版を取得：

```bash
git pull origin main
pip3 install -r requirements.txt --upgrade
```

## 📞 サポート

問題が発生した場合は、以下を確認してください：

1. ログファイル（`logs/trading.log`）
2. APIキーの権限設定
3. ウォレットの残高
4. ネットワーク接続

## 📜 ライセンス

このプロジェクトは教育目的で作成されています。実際の取引は自己責任で行ってください。