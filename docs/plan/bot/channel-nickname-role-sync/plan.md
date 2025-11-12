---
title: "チャンネル別ニックネーム/ロール同期機能 実装計画"
status: "draft"
version: "0.1.0"
domain: "bot"
created: "2025-11-12"
updated: "2025-11-12"
spec_ref: "ニックネーム同期チャンネル リファレンス v0.1.0"
related_docs:
  - "docs/plan/bot/channel-nickname-role-sync/plan.md" # self-reference for future updates
---

## 背景と目的
- Discord サーバー内の特定テキストチャンネルで、投稿者のニックネームとロールを自動的に同期・強制したいという要望があり、仕様書「ニックネーム同期チャンネル リファレンス (beta)」が提示された。
- 現行 `src/` には一時VC管理 (`bot/temp_vc.py`) と簡易送信ビュー (`views/view.py`) のみが実装されており、Slash コマンドや DB 層は最小限。仕様の View / Repository / メッセージフックは未実装。
- 本計画では、仕様を既存アーキテクチャに統合するための作業分解・依存関係・リスクを整理し、実装の進行をガイドする。

## 現状整理
- **設定/DI**: `src/app/config.py` では Discord トークンのみを扱い、DB 設定や Async 初期化は存在しない。`src/app/container.py` は TinyDB を用いた一時VC管理の依存性だけを構築。
- **Discord クライアント**: `src/bot/client.py` は `discord.Client` を継承し、`on_voice_state_update` 以外のイベントをほぼ扱っていない。Slash コマンド登録は `bot/commands.py` に集約。
- **UI**: `src/views/__init__.py` は `SendModalView` のみをエクスポート。View/Modal の構成は単純で、権限制御や複数コンポーネント選択 UI は導入されていない。
- **DB**: PostgreSQL や asyncpg 依存は `pyproject.toml` に存在せず、RDB ベースのストレージは未実装。仕様で求められる `channel_nickname_rules` テーブルもない。
- **ドキュメント**: `docs/` には汎用 README のみ。計画/インテント文書は未作成のため、本ドキュメントが初の plan エントリになる。

## 実装全体像
1. **インフラ層を拡張**し、`asyncpg` を用いた `app.database.Database` を追加。接続時に `channel_nickname_rules` を自動作成し、アプリ終了時に確実に `close()`。
2. **ドメインオブジェクトとリポジトリ** (`ChannelNicknameRule`, `ChannelNicknameRuleRepository`) を `src/bot/nickname_sync/` に配置し、Guild/Channel 毎の設定取得・Upsert をカプセル化。
3. **Slash コマンド `/nickname_sync_setup`** を `bot/commands.py` に登録。View (`views.nickname_sync_setup.NicknameSyncSetupView`) を通じて Text/Announcement チャンネルとロールを選択し、権限/DM/ユーザー検証を満たす。
4. **実行時ガードロジック** (`NicknameSyncService` 仮称) を実装し、`BotClient.on_message` から `enforce_nickname_and_role` を呼び出して本文書き換えとロール付与を行う。Forbidden/HTTPException は WARN ログに留め、処理を継続。
5. **ログ・ドキュメント整備**: `README.md` と関連 docs に新機能のセットアップ手順、権限要件、失敗時のトラブルシュートを追記。

## 詳細タスク

### 1. 依存関係と設定周り
- `pyproject.toml` に `asyncpg` を追加し、ローカル環境では `poetry install` で導入する (CI 設定があるなら追加)。
- `AppConfig` に DB 接続設定 (例: `DATABASE_URL` または `PGHOST/PGUSER` 形式) を追加し、`.env` からの読み込みとバリデーション (`ValueError` on missing)。
- `app/database.py` を新設し、以下を満たす:
  - `Database.connect()` でプール生成 (`asyncpg.create_pool`)、`CREATE TABLE IF NOT EXISTS channel_nickname_rules (...)` を実行。
  - `fetchrow` / `execute` の薄いラッパーを提供し、`async with self._pool.acquire()` でコネクション管理。
  - `close()` が `await pool.close()` を呼ぶ。`DiscordApplication.run()` のライフサイクルに組み込み、Bot 停止時に確実に解放。
- `app/container.py` を更新し、`DiscordApplication` に `database: Database` を保持させる。`build_discord_app` で Database を接続 → `BotClient` へ渡せるよう `nickname_sync_service` などの依存を構築。

### 2. ドメイン層 (Nickname Sync)
- `src/bot/nickname_sync/` ディレクトリを作り、以下を実装:
  - `models.py`: `@dataclass ChannelNicknameRule` (guild_id, channel_id, role_id, updated_by, updated_at)。
  - `repository.py`: `ChannelNicknameRuleRepository` が `Database` を受け取り、`upsert_rule` と `get_rule_for_channel` を実装。asyncpg `Record` から dataclass 生成。
  - `service.py`: `NicknameSyncService` がリポジトリを利用し、`get_rule(guild_id, channel_id)` キャッシュ、`enforce_nickname_and_role(message)` を公開。表示名決定ロジック (display_name → global_name → name) やロール付与サブ処理を内包。
- ロギングポリシー: `INFO` で upsert 成功を記録、`WARNING` でロール未発見や Forbidden を通知。

### 3. Slash コマンド & View
- `bot/commands.py` に `/nickname_sync_setup` を登録:
  - `@discord.app_commands.default_permissions(manage_roles=True, manage_messages=True)` を設定。
  - DM 実行 (`interaction.guild is None`) は即座にエフェメラルで拒否。
  - `NicknameSyncSetupView` を初期化し、`interaction.response.send_message(..., ephemeral=True, view=view)`。
- `views/nickname_sync_setup.py` (および `views/__init__.py` 更新) を作成し、以下の UI コンポーネントを含む:
  - `ChannelSelect` (Text/Announcement 限定) と `RoleSelect` (単一選択) を 1 つずつ。`discord.ui.ChannelSelect` / `discord.ui.RoleSelect` の `channel_types` / `min/max_values` で制約。
  - `Confirm` ボタン押下で選択済みか検証し、`ChannelNicknameRuleRepository.upsert_rule` を await → 結果メッセージ `<#channel>` `<@&role>` を返信、View.stop()。
  - `interaction_check` で実行者/権限チェック (Manage Roles & Manage Messages 所持)。不正時はエフェメラルにて拒否。
  - View がリポジトリ/ギルド ID/ユーザー ID を保持し、`LOGGER.info` で upsert 成功をログ出力。

### 4. Bot クライアント + メッセージ処理
- `BotClient` に `nickname_sync_service: NicknameSyncService | None` を保持し、`__init__` で受け取らない場合は None。
- `BotClient.on_message` をオーバーライドし、以下条件で `await nickname_sync_service.enforce(message)`:
  - `nickname_sync_service` が存在。
  - `message.guild` が存在し、`not message.author.bot`。
  - サービス側で `channel_nickname_rules` に一致する設定がある場合のみ処理。未設定なら即 return。
- `NicknameSyncService.enforce` の詳細:
  - 表示名算出 → `message.content` と不一致なら `message.edit(content=display_name)`。
  - 付与ロールが `Guild.get_role(role_id)` で見つからなければ WARN ログ。
  - メンバーへロール付与 (`member.add_roles`)。`Forbidden`/`HTTPException` は WARN ログで握りつぶし、他エラーは `LOGGER.exception`。
  - 処理結果を DEBUG/INFO レベルで記録。

### 5. ドキュメント & 運用ガイド
- `README.md` に以下を追加:
  - `/nickname_sync_setup` の説明、必要 Bot 権限、PostgreSQL 依存を明記。
  - 新しい環境変数 (例: `DATABASE_URL`) の設定手順。
- `docs/README.md` からこの計画への導線を追記し、将来的に `docs/intent/bot/channel-nickname-role-sync/intent.md` を作成する旨を記す。
- ログ運用: `INFO` (設定変更成功) / `WARN` (ロール未検出, Forbidden) / `ERROR` (DB 接続失敗) のレベル指針を文書化。

### 6. 動作確認とロールアウト
- **ローカル検証**:
  - docker 等で PostgreSQL を起動し、環境変数を設定。
  - Bot を起動し、テストサーバーで `/nickname_sync_setup` を実行 → DB に行が upsert されることを `psql` で確認。
  - 対象チャンネルで通常メッセージを投稿し、メッセージ本文/ロールが同期されるか確認。
- **フェイルセーフ**: DB 接続失敗時には `LOGGER.exception` を出し `build_discord_app` で例外を投げ、Bot 起動を中止 → 明示的なリトライ手順を README に記載。
- **移行**: 既存 TinyDB への影響は無いが、`pyproject` 変更・環境変数追加があるためデプロイ手順の更新 (CI/CD スクリプト, Procfile 等) を計画に含める。

## リスクと対応策
- **DB 未提供環境**: 既存 Bot はファイルベースのみで動いているため、新依存 (PostgreSQL) を導入できない環境がある可能性。→ `.env` で DB を必須にしつつ、実装前にインフラチームへ周知。
- **権限不足による操作失敗**: Manage Roles/Manage Messages を Bot が持たない場合に多数の WARN が出る。→ slash command 実行時に権限を検証し、失敗時は詳細なエラーメッセージを返す。
- **ロール/チャンネル削除後の残存設定**: Repository に残った設定がエラーを引き起こす。→ `NicknameSyncService` で WARN ログを出し、再設定を促すメッセージを設計 (将来の自動クリーンアップは別計画)。
- **同時実行 (メッセージ大量投稿)**: 各メッセージ毎に DB ヒットすると負荷が高い。→ サービス内で Guild/Channel 単位の短期キャッシュを持ち、TTL を設ける方針を検討 (優先度中)。

## 未決事項 / フォローアップ
1. DB 接続情報のフォーマット (単一 DSN vs. individual vars) と Secrets 管理方法。
2. `channel_nickname_rules` にユニーク制約 `(guild_id, channel_id)` を置くが、`role_id` の NOT NULL / FK 制約は必要か。
3. ニックネーム同期対象チャンネル数が多い場合のキャッシュ方針 (LRU, TTL) をどこまで初期リリースに含めるか。
4. 失敗したロール付与をユーザーへ別途通知するか否か (現計画は WARN ログのみ)。
5. Intent/Plan ドキュメント体系 (この plan に合わせた intent 文書) の追加スケジュール。

---
この計画を承認後、上記タスク群を Issue/PR ベースで順次着手する。
