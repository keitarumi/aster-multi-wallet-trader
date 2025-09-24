# Aster Multi-Wallet Trader

複数のウォレット間で相対トレード（両建て）を行い、Discord通知機能を備えた自動取引システム。

## 🚀 特徴

- **自動ウォレット検出**: .envファイルから複数ウォレットを自動認識
- **相対トレード**: 異なるウォレットペアで異なる銘柄を順次両建て
- **自然な取引パターン**: ランダムな遅延とポジションサイズの変動
- **Discord通知**: ポジションオープン/クローズ、残高レポート、エラー通知
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
- 各ウォレットに最低$100 USDTの残高が必要

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

  # シンボルごとのポジションサイズ設定（USDT）
  position_sizes:
    BTCUSDT: 500      # BTC用のポジションサイズ
    ETHUSDT: 500      # ETH用のポジションサイズ
    ASTERUSDT: 1000   # ASTER用のポジションサイズ
    SOLUSDT: 500      # SOL用のポジションサイズ

  # デフォルトポジションサイズ（上記で指定されていないシンボル用）
  default_position_size_usdt: 500

  # ポジションサイズの変動幅
  position_size_variance: 0.3         # ランダム変動幅（30% = 0.3）

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
  send_on_position_open: true        # ポジションオープン時通知
  send_on_position_close: true       # ポジションクローズ時通知
  send_on_error: true                 # エラー時通知
  daily_summary_hour: 9               # 日次サマリー時刻（24時間形式）
  low_balance_threshold: 100          # 残高警告しきい値（USDT）
```

## 📊 使い方

### メイン実行コマンド

```bash
# トレーディングを開始
python3 main.py trade

# システムテスト
python3 main.py test
```

## 📝 トレーディングロジック詳細

### 1. チーム型取引システム

#### 1.1 ウォレットチーム分割
```
例: 4ウォレット (A, B, C, D) の場合
- パターン1: [A] vs [B, C, D] (1:3分割)
- パターン2: [A, B] vs [C, D] (2:2分割)
- パターン3: [A, C] vs [B, D] (シャッフル後2:2)
```
- 毎ラウンドでランダムにチーム構成を変更
- 最低各チーム1ウォレット必須
- BOT検出を回避するため同じパターンを繰り返さない

#### 1.2 数量分配アルゴリズム
```python
総ポジション = 1000 USDT相当
ロングチーム(2ウォレット) → [600 USDT, 400 USDT]
ショートチーム(2ウォレット) → [300 USDT, 700 USDT]
※ ロング合計 = ショート合計 = 1000 USDT
```
- チーム内でランダムな比率で分配
- 最小注文サイズ（$100 USDT）を下回らないよう調整
- 合計値が完全に一致するよう最後のウォレットで微調整

### 2. 取引実行プロセス

#### 2.1 ポジションオープンシーケンス
```
時刻 00:00:00 - ロングチーム実行開始
├─ 00:00:00 - Wallet A: BUY 0.010 BTC
├─ 00:00:01 - Wallet C: BUY 0.006 BTC (1秒遅延)
├─ 00:00:02 - チーム間待機 (1秒)
└─ 00:00:03 - ショートチーム実行開始
   ├─ 00:00:03 - Wallet B: SELL 0.008 BTC
   └─ 00:00:04 - Wallet D: SELL 0.008 BTC (1秒遅延)
```

#### 2.2 ポジションクローズシーケンス
```
時刻 00:01:00 - クローズ開始（保有時間1分後）
├─ 00:01:00 - Wallet A: クローズ
├─ 00:01:01 - Wallet C: クローズ
├─ 00:01:02 - Wallet B: クローズ
└─ 00:01:03 - Wallet D: クローズ
```

### 3. リスク管理メカニズム

#### 3.1 残高チェック
- 起動時: $100 USDT未満のウォレットは自動除外
- 実行中: 残高不足時は該当ウォレットをスキップ
- 警告: Discord通知で残高低下を報告

#### 3.2 エラーハンドリング
- **部分的失敗**: 一部の注文が失敗した場合、成功した注文をロールバック
- **API エラー**: 3回リトライ後、次のラウンドまで待機
- **緊急停止**: Ctrl+C で全ポジションを安全にクローズ

#### 3.3 最小注文サイズ保証
```
BTC: 最小 0.001 BTC または $100 USDT の大きい方
ETH: 最小 0.01 ETH または $100 USDT の大きい方
SOL: 最小 1 SOL または $100 USDT の大きい方
```

### 4. タイミング制御

#### 4.1 各種遅延設定
- **wallet_execution_delay**: ウォレット間の実行遅延（1秒）
- **ポジション保有時間**: 1-1分（設定可能）
- **ラウンド間クールダウン**: 10-30秒（ランダム）

#### 4.2 自然な取引パターン
```
ラウンド1: BTC取引 → 70秒待機
ラウンド2: ETH取引 → 25秒待機
ラウンド3: ASTER取引 → 18秒待機
```
- 銘柄選択はランダム
- 待機時間もランダム
- 人間らしい不規則性を演出

### 5. データベース記録

#### 5.1 記録される情報
- **trades テーブル**: 個別の売買記録
- **positions テーブル**: ヘッジポジション情報
- **position_trades テーブル**: ポジションと取引の紐付け
- **daily_summary テーブル**: 日次統計

#### 5.2 パフォーマンス分析
```sql
-- 成功率計算
SELECT COUNT(*) as total,
       SUM(CASE WHEN total_pnl >= 0 THEN 1 ELSE 0 END) as profitable
FROM positions WHERE status = 'CLOSED';
```

### 6. Discord通知

#### 6.1 通知タイミング
- ポジションオープン時
- ポジションクローズ時
- エラー発生時
- 定期レポート（1時間毎）
- 日次サマリー（毎朝9時）

#### 6.2 通知内容
```
📈 Position Opened
Symbol: BTCUSDT
Long Team: Wallet A (0.006), Wallet C (0.004)
Short Team: Wallet B (0.007), Wallet D (0.003)
Total: 0.010 BTC
Hold Time: 1.0 minutes
```

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
├── main.py                 # メインエントリーポイント
├── config.yaml             # 設定ファイル
├── .env                    # 環境変数（APIキー）
├── requirements.txt        # 依存関係
├── src/                    # ソースコード
│   ├── multi_wallet_trader.py   # メインの取引システム
│   ├── discord_reporter.py      # Discord通知機能
│   └── database_manager.py      # データベース管理クラス
├── utils/                  # ユーティリティ
│   └── db_query.py        # データベースクエリツール
├── scripts/                # スクリプト
│   └── fetch_prices.py    # 価格取得スクリプト
├── test/                   # テストスクリプト
│   ├── test_simple_trade.py
│   ├── test_two_wallets.py
│   ├── test_team_trading.py
│   ├── test_wallet_detection.py
│   └── test_discord_webhook.py
├── data/                   # データファイル
│   └── trades.db          # 取引履歴データベース（自動生成）
├── logs/                   # ログファイル
│   └── trading.log
└── docs/                   # ドキュメント
```

## 📜 免責事項

このプロジェクトは教育目的で作成されています。実際の取引は自己責任で行ってください。