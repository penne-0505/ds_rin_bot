# Railway デプロイガイド（2025 年更新版）

## このガイドについて
- GitHub 連携と Railpack ベースのビルドを利用して、ds-rin-bot を Railway に継続デプロイする最新フローをまとめています。
- 2025 年時点での Railway ドキュメント（Railpack, Config as Code, Variables, CLI ガイド）を再確認した内容に基づいており、旧 Nixpacks 設定を置き換えています。

## 全体像
1. リポジトリを Railway 向けに準備する（`railway.json` でビルド/起動コマンドを明示）。
2. Railway プロジェクトを作成し、GitHub リポジトリを接続。
3. マネージド PostgreSQL サービスを追加し、環境変数を連携。
4. 初回デプロイを実行し、ログ・メトリクスを確認。
5. 運用時に CLI や再デプロイ機能を活用して監視・トラブルシュート。

---

## 1. リポジトリ準備
### `railway.json` を追加
Railway はコード内の設定ファイルを優先的に読み取り、ビルドと起動のコマンドを上書きできます。Poetry プロジェクトの場合、以下の `railway.json` をリポジトリ直下に追加することで、Railpack が Poetry を自動インストールしないケースを回避できます。

```json
{
  "$schema": "https://railway.com/railway.schema.json",
  "build": {
    "builder": "RAILPACK",
    "buildCommand": "poetry install --no-root --only main"
  },
  "deploy": {
    "startCommand": "poetry run python src/main.py"
  }
}
```
- `builder` を明示しなくても Railpack が既定ですが、明示すると設定ファイル内で上書きしたことがデプロイ履歴から確認しやすくなります。
- 依存パッケージを開発環境と揃えたい場合は `--with dev` を付けるなど、必要に応じてコマンドを変更してください。

### Python バージョンの固定
Railpack は `pyproject.toml` の `python` セクションを参照します。`[tool.poetry.dependencies]` に `python = "^3.12"` のように明示し、想定バージョンを固定します。必要であれば Railway の `Variables` タブで `PYTHON_VERSION=3.12.4` などを追加し、実行環境と揃えてください。

### シークレットの取り扱い
`.env.example` に必要なキー（`DISCORD_BOT_TOKEN`, `DATABASE_URL` など）を列挙し、コミット対象から除外した `.env` でローカル開発を行います。Railway 上の値とは分離して管理します。

---

## 2. Railway プロジェクトの作成
1. [Railway ダッシュボード](https://railway.com/dashboard) で **New Project** をクリックします。
2. **Deploy from GitHub repo** を選び、ds-rin-bot のリポジトリを接続します。初回は GitHub App のインストール許可が求められるため、対象リポジトリを選択して承認してください。
3. デプロイ対象の Branch（通常は `main` もしくは `master`）を指定し、プロジェクト作成を完了します。
4. 初回デプロイは設定変更前に走らせないよう、`Pause Auto Deploys` を選択しておくと安全です。

---

## 3. PostgreSQL サービスの追加
1. プロジェクトキャンバスで **Add Service** → **Database** → **PostgreSQL** を選択します。
2. 作成後に `DATABASE_URL`, `PGHOST`, `PGUSER`, `PGPASSWORD` などの変数が自動生成されます。`DATABASE_URL` を Bot サービスで再利用するため、値をコピーしておきます。
3. 必要に応じて `Backups` を有効化し、自動スナップショットのスケジュールを確認します。

---

## 4. サービス変数の設定
### ダッシュボードでの設定
1. GitHub からデプロイされたサービスを開き、`Variables` タブに移動します。
2. 以下のキーを追加または再マッピングします。
   - `DISCORD_BOT_TOKEN`: Discord Developer Portal で取得した Bot トークン。
   - `DATABASE_URL`: PostgreSQL サービスの `DATABASE_URL` を「Reference」機能でリンク（`Add Variable` → `Reference Variable`）。
   - その他、必要に応じて `DISCORD_GUILD_ID` などの追加変数を設定。
3. 値を保存後、`Restart` を実行して反映を確認します。

### CLI での設定（任意）
自動化する場合は Railway CLI を利用します。
```bash
# ログインとプロジェクトの関連付け
railway login
railway link --environment production

# 変数設定（Reference ではなく値を直接設定する場合）
railway variables set DISCORD_BOT_TOKEN=xxxxx
railway variables set DATABASE_URL=$(railway variables get -s <postgres-service-id> DATABASE_URL)
```
- CLI ではサービスごとに ID が異なるため、`railway status` で対象サービスの ID を確認してからコマンドを実行します。

---

## 5. デプロイと検証
1. GitHub の `main` ブランチへ push すると自動でデプロイが走ります。`Deployments` タブで `Queued → Building → Deploying → Healthy` のステータス遷移を確認してください。
2. ログは `Deployments` → 対象デプロイ → `Logs` から確認できます。`Bot is ready.` が表示され、Discord 側でオンライン表示に変われば成功です。
3. Config as Code を使っている場合、デプロイ詳細画面にファイルアイコンが表示され、`railway.json` 内の値が反映されているか確認できます。
4. エラーが発生した場合は `Rebuild` を押して再試行するか、CLI から `railway redeploy <deployment-id>` を実行して再デプロイします。

---

## 6. 運用のヒント
- **再デプロイ**: 直前のビルドをそのまま再利用したい場合は `railway redeploy` を使うとダウンタイムを抑えられます。
- **ログとメトリクス**: `railway logs -f` でリアルタイムログを追跡しつつ、ダッシュボードの `Metrics` から CPU・メモリのトレンドを確認します。
- **リージョン選択**: [Deployment Regions](https://docs.railway.com/reference/deployment-regions) に記載の通り、ユーザーが多い地域に近いリージョンを選ぶことでレイテンシ削減が可能です。Config as Code の `deploy.multiRegionConfig` を使うとマルチリージョン展開も構成できます。
- **Secrets 管理**: チームで運用する場合は `Members` 権限を確認し、機密情報の閲覧が不要なメンバーには `Viewer` 権限を付与します。
- **ヘルスチェック**: Web エンドポイントを提供する場合は `deploy.healthcheckPath` を設定すると、Railway が起動後に自動チェックを行い、不安定なデプロイをロールバックできます（Bot 単体では不要ですが、Slash コマンドの補助 API を増設する際に活用できます）。

---

## 7. トラブルシューティング
| 症状 | 想定原因 | 対処 |
| ---- | -------- | ---- |
| `poetry: command not found` | `railway.json` で `buildCommand` を指定していない / Poetry のインストールがスキップされた | `railway.json` を追加し、再デプロイする。もしくは `buildCommand` に `pip install poetry` を含める |
| `KeyError: 'DATABASE_URL'` | サービス側で変数が未設定、または Reference のリンク切れ | `Variables` タブで値を再設定し、`Restart` を実行 |
| Discord 側で Offline のまま | Bot トークンが無効、Intents 設定が不足、`DISCORD_BOT_TOKEN` を更新後に再起動していない | Discord Developer Portal でトークン・Privileged Intents を確認し、Railway の変数を更新して再デプロイ |
| デプロイが `Build Failed` | `pyproject.toml` の依存解決エラー、Python バージョン不一致 | ログを確認し、`python` のバージョン指定や依存関係を見直してから再ビルド |

---

これで Railway 上での ds-rin-bot 運用準備が整いました。Config as Code によりビルド／デプロイ設定をリポジトリで追跡できるため、Pull Request ベースで変更レビューを行いつつ、Railway CLI を活用して本番環境を安全に管理してください。
