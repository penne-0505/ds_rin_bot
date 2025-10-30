# ブリッジメッセージ記録のメンテナンス

`ChannelBridgeManager` はブリッジ処理で使用した表示名・アイコンURL・DiceBear失敗フラグ・送信先メッセージID・添付ファイル要約を `data/bridge_messages.json` に保存します。TinyDB の `bridge_messages` テーブルに 1 メッセージあたり 1 レコードが作成され、編集同期時に再利用されます。

## レコードの定期削除

ブリッジ済みメッセージは 24 時間を超えると編集される可能性が低いため、定期タスクや cron などから次のスクリプトを実行し、古いレコードを削除してください。

```bash
python - <<'PY'
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tinydb import TinyDB

from bot.bridge.messages import BridgeMessageStore

store = BridgeMessageStore(TinyDB(Path("data") / "bridge_messages.json"))
removed = store.purge_older_than(
    threshold=datetime.now(timezone.utc) - timedelta(hours=24)
)
print(f"Removed {removed} expired bridge message records.")
PY
```

任意の保持期間に合わせて `timedelta` を調整してください。削除後も新しいブリッジ処理時にレコードが自動再生成されます。

## ブリッジ設定変更時の再同期

チャンネルルート設定 (`data/channel_routes.json`) を更新した場合は、以下の手順でレコードの再同期を行います。

1. Bot を停止する。
2. 影響範囲のレコードを削除する。設定全体を差し替えた場合は `data/bridge_messages.json` を削除するか、上記スクリプトで全件削除 (`timedelta(0)`) を実行する。
3. Bot を再起動して新しいルートを読み込み、必要に応じて元メッセージを編集し直すか、新規メッセージを送信してブリッジを再作成する。

この手順により、`ChannelBridgeManager` が新しいルートに基づいたメッセージリンクとメタデータを再構築できます。
