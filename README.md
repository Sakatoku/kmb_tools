# backlog_notifier

Backlog API を使って、特定プロジェクトの「一定時間以内に更新・新規追加されたチケット」を取得し、HTML メールを `.eml` ファイルとして出力する Python ツールです。

## セットアップ

```bash
# 依存ライブラリのインストール
pip install -r requirements.txt

# 設定ファイルの準備
cp backlog_notifier/config.yaml.example backlog_notifier/config.yaml
# config.yaml を編集して接続情報を入力してください
```

## 設定ファイル (`config.yaml`)

```yaml
backlog:
  space_id: "your-space"       # Backlog スペースID（https://your-space.backlog.com の "your-space"）
  api_key: "your-api-key"      # Backlog API キー（個人設定 → API から発行）
  project_key: "YOUR_PROJECT"  # 対象プロジェクトのキー
  hours: 24                    # この時間（時）以内に更新されたチケットを対象にする

email:
  from: "sender@example.com"
  to: "recipient@example.com"
  subject: "Backlog 更新チケット通知"
  output_dir: "./output"       # 生成する .eml ファイルの出力ディレクトリ
```

| キー | 説明 |
|------|------|
| `backlog.space_id` | Backlog スペースID。`https://<space_id>.backlog.com` の部分 |
| `backlog.api_key` | Backlog 個人 API キー |
| `backlog.project_key` | 対象プロジェクトのキー（例: `MYPROJ`） |
| `backlog.hours` | 何時間以内に更新されたチケットを対象にするか |
| `email.from` | 送信元メールアドレス |
| `email.to` | 宛先メールアドレス |
| `email.subject` | メール件名 |
| `email.output_dir` | 生成する `.eml` ファイルの保存先ディレクトリ |

## 実行

```bash
# デフォルト設定ファイル (backlog_notifier/config.yaml) を使用
python -m backlog_notifier.main

# 設定ファイルのパスを指定
python -m backlog_notifier.main --config /path/to/config.yaml
```

実行後、`output_dir` に `backlog_notify_YYYYMMDD_HHMMSS.eml` ファイルが生成されます。

## 出力例

生成された `.eml` ファイルをメールクライアント（Outlook・Thunderbird など）で開くと、以下のようなHTMLメールとして表示されます。

- プロジェクト名と対象時間帯のサマリー
- チケット一覧テーブル（種別バッジ・チケットID・件名・状態・担当者・更新日時）
- チケットIDは Backlog へのリンク付き

## メール種別バッジ

| バッジ | 意味 |
|--------|------|
| 🟢 新規追加 | 対象期間内に作成されたチケット |
| 🟡 更新 | 対象期間内に更新されたチケット（作成は期間外） |

## ファイル構成

```
kmb_tools/
├── backlog_notifier/
│   ├── __init__.py
│   ├── main.py              # エントリーポイント
│   ├── backlog_client.py    # Backlog API クライアント
│   ├── email_builder.py     # EML ファイル生成
│   └── config.yaml.example  # 設定ファイルのテンプレート
├── requirements.txt
└── README.md
```
