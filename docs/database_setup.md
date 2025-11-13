# PostgreSQL 環境構築ガイド

## このガイドの目的
- ds-rin-bot が利用する `channel_nickname_rules` テーブルなどの永続データを保持するための PostgreSQL を、安全に構築・運用する手順をまとめています。
- 開発用のローカル環境と、本番/ステージングのホスティングサービス（Railway や Supabase など）で共通して押さえるべきポイントを整理しました。

## 推奨要件
| 項目 | 推奨値 | 補足 |
| ---- | ------ | ---- |
| PostgreSQL バージョン | 15 〜 16 系 | `asyncpg` で動作確認済みの安定版。新規セットアップでは 16.x を推奨 |
| 認証方式 | `scram-sha-256` | デフォルトの `md5` より安全です。`postgresql.conf` と `pg_hba.conf` を併せて調整してください |
| リスンアドレス | `0.0.0.0`（リモート接続）/ `localhost`（ローカル） | 外部公開する場合はファイアウォールや VPC で接続元を制限 |
| バックアップ | 1 日 1 回以上 | `pg_dump`、マネージドサービスの自動スナップショットなどを活用 |

## セットアップ手順
1. [PostgreSQL のインストール](#postgresql-のインストール)
2. [データベースとロールの作成](#データベースとロールの作成)
3. [接続確認](#接続確認)
4. [Bot からの接続設定](#bot-からの接続設定)
5. [運用時のベストプラクティス](#運用時のベストプラクティス)

### PostgreSQL のインストール
#### Docker（推奨）
```bash
# 作業ディレクトリは任意
mkdir -p ~/postgres/data

# 公式イメージを利用して 16 系を起動
docker run -d \
  --name ds-rin-postgres \
  -e POSTGRES_USER=dsrin \
  -e POSTGRES_PASSWORD=dsrinpass \
  -e POSTGRES_DB=ds_rin_bot \
  -e POSTGRES_INITDB_ARGS='--data-checksums' \
  -p 5432:5432 \
  -v ~/postgres/data:/var/lib/postgresql/data \
  postgres:16
```
- `--data-checksums` を指定すると、ディスク障害によるデータ破損を検知しやすくなります（初期化時のみ有効）。
- 既存プロセスとポートが重複する場合は `-p 15432:5432` のようにホスト側ポートを変更してください。

#### パッケージマネージャ
- **macOS (Homebrew)**: `brew install postgresql@16`
- **Debian / Ubuntu**: `sudo apt install postgresql`
- **Windows**: [PostgreSQL 公式インストーラ](https://www.postgresql.org/download/windows/) を利用してください。

インストール後は `psql --version` を実行し、意図したバージョンであることを確認します。サービスの起動状態は `systemctl status postgresql` で確認できます。

### データベースとロールの作成
Docker 例のように環境変数を指定した場合は自動作成されます。手動で構築した場合は次のコマンドを実行してください。

```bash
# 管理者ユーザーで psql を開く
sudo -u postgres psql

-- 以下は psql 内で実行
CREATE ROLE dsrin WITH LOGIN PASSWORD '強固なパスワードを設定';
CREATE DATABASE ds_rin_bot OWNER dsrin ENCODING 'UTF8';
GRANT ALL PRIVILEGES ON DATABASE ds_rin_bot TO dsrin;
ALTER ROLE dsrin SET search_path TO public;
```
- パスワードは推測されにくい長さ・複雑性を持つものに変更してください。
- リモート接続を受け付ける場合、`pg_hba.conf` に `host all dsrin 0.0.0.0/0 scram-sha-256` のような設定を追加します。CIDR は必要最小限に絞ってください。

### 接続確認
1. クライアント端末から TCP 接続できるか確認します。
   ```bash
   PGPASSWORD='(設定したパスワード)' psql \
     --host=localhost \
     --port=5432 \
     --username=dsrin \
     --dbname=ds_rin_bot \
     --command='SELECT version();'
   ```
2. 正常にバージョン情報が返れば接続成功です。失敗する場合はファイアウォール、`pg_hba.conf`、パスワードなどを順に確認してください。

### Bot からの接続設定
1. プロジェクトルートに `.env` を作成し、最低限次の値を設定します。
   ```env
   DISCORD_BOT_TOKEN=取得した Bot トークン
   DATABASE_URL=postgresql://dsrin:パスワード@localhost:5432/ds_rin_bot
   ```
2. マネージドサービスを利用する場合は、Railway などが発行する接続文字列（例: `postgresql://user:pass@host:port/db?sslmode=require`）をそのまま `DATABASE_URL` に設定します。
3. Bot を起動すると `src/app/database.py` が `channel_nickname_rules` テーブルを検査し、未作成であれば自動作成します。初回起動時のログで「データベース接続と初期化が完了しました」と表示されることを確認してください。

### 運用時のベストプラクティス
- **バックアップ**: `pg_dump` での論理バックアップに加え、スナップショット型バックアップ（マネージドサービスの自動スナップショットなど）を定期的に取得し、復元手順を検証しましょう。
- **監視**: 接続数、ディスク使用量、`autovacuum` の遅延などをメトリクスとして収集します。Docker 運用の場合は `docker exec ds-rin-postgres pg_stat_activity` などで状態を確認できます。
- **メンテナンス**: メジャーアップデートを適用する場合は本番環境のバックアップを取得し、開発環境で互換性を確認してから切り替えます。
- **セキュリティ**: パブリックネットワークに公開する場合はセキュリティグループやファイアウォールで接続元を制限し、Cloudflare Tunnel や SSH ポートフォワードなどで間接的にアクセスする構成を検討してください。

以上で PostgreSQL のセットアップは完了です。Bot の起動前に `.env` の値と接続確認を再チェックし、問題があればログと設定ファイルを突き合わせて原因を切り分けてください。
