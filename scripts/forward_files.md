# forward_files.sh ドキュメント

## 概要

`forward_files.sh` は、Linux サーバ上の特定ディレクトリに出力されたファイルを定期的に収集し、SCP で別サーバへ転送するシェルスクリプトである。cron により5分ごとに実行される。

転送対象ファイルは処理の冒頭でステージングディレクトリへ移動してから転送を行う設計となっており、転送に5分以上要した場合でも次回の cron 実行と処理が重複しない。

### 実行方法

```sh
# 通常実行
forward_files.sh

# ドライランモード（ファイル移動・SCP は一切行わない）
forward_files.sh --dry-run
```

---

## 基本設計書

### 1. システム構成

```
[転送元サーバ]                          [転送先サーバ]
/var/data/source/          SCP          /data/incoming/
  *.csv (対象ファイル)  ──────────────►  (受信ディレクトリ)
       │
       │ mv（処理冒頭）
       ▼
/mnt/tmp/forward-{RAND}/
  (ステージングディレクトリ)
       │
       │ 転送失敗時
       ▼
/mnt/tmp/failure-{RAND}/
  (失敗ファイル保管)
```

### 2. 実行環境

| 項目 | 内容 |
|---|---|
| 実行シェル | `/bin/sh`（POSIX 準拠） |
| 実行方式 | cron（5分間隔）。`--dry-run` オプションで手動確認も可能 |
| 必要コマンド | `scp`, `find`, `mv`, `rm`, `mkdir`, `tr`, `fold`, `cat`, `basename`, `date` |

### 3. 設定パラメータ

スクリプト上部の変数で環境ごとの設定を行う。

| 変数名 | デフォルト値 | 説明 |
|---|---|---|
| `SOURCE_DIR` | `/var/data/source` | 転送元ディレクトリ |
| `FILE_PATTERN` | `*.csv` | 転送対象ファイルの glob パターン |
| `STAGING_BASE` | `/mnt/tmp` | ステージング・失敗ディレクトリのベースパス |
| `SCP_USER` | `transfer` | SCP 接続ユーザ名 |
| `SCP_HOST` | `192.168.1.100` | SCP 転送先ホスト |
| `SCP_DEST_DIR` | `/data/incoming` | 転送先ディレクトリ |
| `SCP_KEY` | `/home/transfer/.ssh/id_rsa` | SSH 秘密鍵パス |
| `SCP_PORT` | `22` | SSH ポート番号 |
| `LOG_DIR` | `/var/log/kmb` | ログ出力ディレクトリ |

### 4. 処理フロー

```
起動
 │
 ├─ ランダム文字列（8文字英数字）生成 → RAND
 │
 ├─ [1] 対象ファイル確認
 │       SOURCE_DIR 内の FILE_PATTERN に一致するファイルを検索
 │       ファイルが0件 → ログ出力して正常終了
 │
 ├─ [2] ステージングディレクトリ作成
 │       /mnt/tmp/forward-{RAND}/ を作成
 │       作成失敗 → エラーログ出力して異常終了
 │
 ├─ [3] ファイル移動（mv）
 │       SOURCE_DIR の対象ファイルをステージングディレクトリへ移動
 │       ※ この時点で次回 cron 実行の対象外となり、重複処理を防ぐ
 │       移動できたファイルが0件 → ログ出力して正常終了
 │
 ├─ [4] SCP 転送（試行1回目）
 │       ステージングディレクトリ内の全ファイルを転送先へ送信
 │       成功 → [6] へ
 │       失敗 → ログ出力して試行2回目へ
 │
 ├─ [5] SCP 転送（試行2回目・リトライ）
 │       成功 → [6] へ
 │       失敗 → [7] へ
 │
 ├─ [6] 転送成功処理
 │       ステージングディレクトリを削除
 │       正常終了（exit 0）
 │
 └─ [7] 転送失敗処理
         /mnt/tmp/failure-{RAND}/ を作成
         ステージングディレクトリ内のファイルを failure ディレクトリへ移動
         失敗ファイル名をログに記録（FAILED_FILE: <filename>）
         異常終了（exit 1）
```

### 5. ディレクトリ命名規則

スクリプト起動時に `/dev/urandom` から英小文字・数字8文字のランダム文字列（`RAND`）を生成し、ステージングディレクトリと失敗ディレクトリの両方に同じ文字列を使用する。

| ディレクトリ | パス例 |
|---|---|
| ステージング | `/mnt/tmp/forward-a3f8k2qz` |
| 失敗ファイル | `/mnt/tmp/failure-a3f8k2qz` |

ランダム文字列は起動ごとに変わるため、同時刻に複数プロセスが起動してもディレクトリが衝突しない。  
また、同一文字列を使うことでログ上でステージングと失敗ディレクトリの対応を即座に特定できる。

### 6. 重複実行防止の設計

転送処理の前にファイルを `mv` でステージングディレクトリへ移動する。`mv` は同一ファイルシステム内ではアトミックに動作するため、次回 cron 実行が始まった時点で `SOURCE_DIR` に対象ファイルは存在せず、処理の重複が発生しない。

```
時刻  T+0:00  cron 起動 → ファイルを mv → SCP 転送開始
時刻  T+5:00  次の cron 起動 → SOURCE_DIR にファイルなし → スキップ
時刻  T+7:00  前回の SCP 転送完了
```

### 7. SCP リトライ仕様

| 項目 | 内容 |
|---|---|
| 最大試行回数 | 2回（初回 + リトライ1回） |
| リトライ間隔 | なし（即時） |
| 接続タイムアウト | 30秒（`ConnectTimeout=30`） |
| 2回失敗時の動作 | 失敗ファイルを `/mnt/tmp/failure-{RAND}/` へ移動、exit 1 |

### 8. ログ仕様

| 項目 | 内容 |
|---|---|
| 出力先 | `/var/log/kmb/forward_YYYYMMDD.log` |
| ローテーション | 日付ごとにファイルが切り替わる（自動削除は行わない） |
| フォーマット | `YYYY-MM-DD HH:MM:SS [PID] メッセージ` |

#### ログレベルとキーワード

| キーワード | 意味 |
|---|---|
| `=== START ===` | スクリプト起動 |
| `=== END ===` | 正常終了 |
| `=== END (error) ===` | 異常終了 |
| `WARNING:` | 注意が必要だが処理は継続 |
| `ERROR:` | 処理が失敗または中断 |
| `FAILED_FILE:` | SCP 転送失敗ファイルのファイル名 |

#### ログ出力例（ドライラン時）

```
2026-03-26 05:32:00 [12345] === START staging_dir=/mnt/tmp/forward-a3f8k2qz dry_run=1 ===
2026-03-26 05:32:00 [12345] Files found: 3
2026-03-26 05:32:00 [12345] [DRY-RUN] Would create staging directory: /mnt/tmp/forward-a3f8k2qz
2026-03-26 05:32:00 [12345] [DRY-RUN] Would move: /var/data/source/data_01.csv -> /mnt/tmp/forward-a3f8k2qz/data_01.csv
2026-03-26 05:32:00 [12345] [DRY-RUN] Would move: /var/data/source/data_02.csv -> /mnt/tmp/forward-a3f8k2qz/data_02.csv
2026-03-26 05:32:00 [12345] [DRY-RUN] Would move: /var/data/source/data_03.csv -> /mnt/tmp/forward-a3f8k2qz/data_03.csv
2026-03-26 05:32:00 [12345] [DRY-RUN] Would transfer to: transfer@192.168.1.100:/data/incoming
2026-03-26 05:32:00 [12345] === END (dry-run) ===
```

#### ログ出力例（正常時）

```
2026-03-26 04:40:00 [12345] === START staging_dir=/mnt/tmp/forward-a3f8k2qz ===
2026-03-26 04:40:00 [12345] Files found: 3
2026-03-26 04:40:00 [12345] Moved: /var/data/source/data_01.csv -> /mnt/tmp/forward-a3f8k2qz/data_01.csv
2026-03-26 04:40:00 [12345] Moved: /var/data/source/data_02.csv -> /mnt/tmp/forward-a3f8k2qz/data_02.csv
2026-03-26 04:40:00 [12345] Moved: /var/data/source/data_03.csv -> /mnt/tmp/forward-a3f8k2qz/data_03.csv
2026-03-26 04:40:00 [12345] Move complete. moved=3 failed=0
2026-03-26 04:40:00 [12345] SCP transfer started (attempt 1/2): transfer@192.168.1.100:/data/incoming
2026-03-26 04:40:02 [12345] SCP transfer succeeded
2026-03-26 04:40:02 [12345] Staging directory removed: /mnt/tmp/forward-a3f8k2qz
2026-03-26 04:40:02 [12345] === END ===
```

#### ログ出力例（SCP 失敗時）

```
2026-03-26 04:40:00 [12345] === START staging_dir=/mnt/tmp/forward-a3f8k2qz ===
2026-03-26 04:40:00 [12345] Files found: 2
2026-03-26 04:40:00 [12345] Move complete. moved=2 failed=0
2026-03-26 04:40:00 [12345] SCP transfer started (attempt 1/2): transfer@192.168.1.100:/data/incoming
2026-03-26 04:40:05 [12345] WARNING: SCP transfer failed (attempt 1/2, exit=1) output=ssh: connect to host...
2026-03-26 04:40:05 [12345] Retrying SCP transfer (attempt 2/2)...
2026-03-26 04:40:10 [12345] ERROR: SCP transfer failed (attempt 2/2, exit=1) output=ssh: connect to host...
2026-03-26 04:40:10 [12345] Moving failed files to: /mnt/tmp/failure-a3f8k2qz
2026-03-26 04:40:10 [12345] FAILED_FILE: data_01.csv
2026-03-26 04:40:10 [12345] FAILED_FILE: data_02.csv
2026-03-26 04:40:10 [12345] Failed files moved to: /mnt/tmp/failure-a3f8k2qz
2026-03-26 04:40:10 [12345] === END (error) ===
```

### 9. cron 設定例

```cron
*/5 * * * * /path/to/forward_files.sh
```

### 10. 障害対応

| 状況 | 確認方法 | 対応 |
|---|---|---|
| SCP 転送失敗 | ログの `ERROR:` / `FAILED_FILE:` を確認 | `/mnt/tmp/failure-{RAND}/` 内のファイルを手動で再送 |
| `FAILED_FILE:` の一覧抽出 | `grep "FAILED_FILE:" /var/log/kmb/forward_YYYYMMDD.log` | — |
| ステージングが残留 | `/mnt/tmp/forward-*/` の有無を確認 | failure ディレクトリ作成失敗時のみ残留。手動で再送後に削除 |
