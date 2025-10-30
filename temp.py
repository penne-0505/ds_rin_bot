"""
================================================================================
タイトル: 複数サーバー対応Discordメッセージ転送Bot
説明: 特定チャンネル間でメッセージを転送し、リアクションも同期するBot。
       今後サーバーを増やしても対応可能な構成に改良済み。

1. Bot概要
-----------
- メッセージ転送: 指定チャンネル間でメッセージをEmbedとして転送
- 架空送信者: ランダムな名前とアイコンで送信者を装飾
- 添付ファイル転送: 画像などの添付も転送（1枚目はEmbed表示）
- リアクション同期: 双方向でリアクションの追加・削除を反映
- 永続化: message_map.json にメッセージID対応関係を保存
- 拡張性: channel_config.json でチャンネルペアを自由に追加可能

2. ファイル構成
-----------
- discord_mirror_bot.py : Bot本体コード（このファイル）
- message_map.json      : メッセージIDの対応関係を保存
- channel_config.json   : 転送チャンネル設定（srcとdstのペアをJSONで管理）

3. channel_config.json の例
-----------
[
  { "src": 111111111111111111, "dst": 222222222222222222 },
  { "src": 222222222222222222, "dst": 111111111111111111 },
  { "src": 333333333333333333, "dst": 444444444444444444 },
  { "src": 444444444444444444, "dst": 333333333333333333 }
]

- src: 転送元チャンネルID
- dst: 転送先チャンネルID
- 複数サーバー・複数チャンネルペアを自由に追加可能

================================================================================
"""

import discord, json, os, random
from discord.ext import commands

# ---------------------------
# Bot設定
# ---------------------------
TOKEN = "YOUR_BOT_TOKEN"  # ここにBotトークンを入力

MAP_FILE = "message_map.json"
CONFIG_FILE = "channel_config.json"

PROFILES = [
    {"n": "狐の伝令", "i": "https://i.imgur.com/2yaf2wb.png"},
    {"n": "桜の精", "i": "https://i.imgur.com/5yCjM8E.png"},
    {"n": "夜空の旅人", "i": "https://i.imgur.com/Rlq0SYV.png"},
    {"n": "影の語り部", "i": "https://i.imgur.com/wg2O8iW.png"},
    {"n": "霧の観測者", "i": "https://i.imgur.com/XDVR4yu.png"}
]

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.guilds = True

bot = commands.Bot("!", intents=intents)

# ---------------------------
# データ構造
# ---------------------------
mmap = {}   # メッセージIDマップ
CONFIG = [] # チャンネルペア設定

# ---------------------------
# データ読み書き
# ---------------------------
def load_map():
    global mmap
    if os.path.exists(MAP_FILE):
        with open(MAP_FILE, "r", encoding="utf-8") as f:
            mmap = {int(k): int(v) for k, v in json.load(f).items()}

def save_map():
    with open(MAP_FILE, "w", encoding="utf-8") as f:
        json.dump(mmap, f, ensure_ascii=False)

def load_config():
    global CONFIG
    if not os.path.exists(CONFIG_FILE):
        sample = [
            {"src": 111111111111111111, "dst": 222222222222222222},
            {"src": 222222222222222222, "dst": 111111111111111111}
        ]
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(sample, f, ensure_ascii=False, indent=2)
        CONFIG = sample
        print("📝 サンプル設定ファイル生成:", CONFIG_FILE)
    else:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            CONFIG = json.load(f)
        print(f"🔧 {len(CONFIG)} 件の転送設定読み込み")

# ---------------------------
# Botイベント
# ---------------------------
@bot.event
async def on_ready():
    load_map()
    load_config()
    print(f"✅ {bot.user} 起動")

@bot.event
async def on_message(m):
    if m.author.bot or not m.guild:
        return
    for pair in CONFIG:
        src, dst = pair["src"], pair["dst"]
        if m.channel.id == src:
            c = bot.get_channel(dst)
            if not c:
                print(f"⚠️ 転送先チャンネル {dst} が見つかりません")
                continue
            p = random.choice(PROFILES)
            e = discord.Embed(description=m.content or "‎", color=0x00BFFF)
            e.set_author(name=p["n"], icon_url=p["i"])
            e.set_footer(text=f"From {m.author} | {m.guild.name}")
            files = []
            if m.attachments:
                e.set_image(url=m.attachments[0].url)
                files = [await a.to_file() for a in m.attachments[1:]]
            s = await c.send(embed=e, files=files)
            mmap[m.id] = s.id
            mmap[s.id] = m.id
            save_map()
    await bot.process_commands(m)

# ---------------------------
# リアクション同期
# ---------------------------
async def react_sync(r, user, add=True):
    if user.bot or r.message.id not in mmap:
        return
    mid = mmap[r.message.id]
    for pair in CONFIG:
        if r.message.channel.id in (pair["src"], pair["dst"]):
            ch = bot.get_channel(pair["dst"] if r.message.channel.id == pair["src"] else pair["src"])
            if not ch:
                return
            msg = await ch.fetch_message(mid)
            try:
                if add:
                    await msg.add_reaction(r.emoji)
                else:
                    await msg.clear_reaction(r.emoji)
            except:
                pass
            break

@bot.event
async def on_reaction_add(r, u): await react_sync(r, u, True)
@bot.event
async def on_reaction_remove(r, u): await react_sync(r, u, False)
@bot.event
async def on_disconnect(): save_map()

# ---------------------------
# Bot起動
# ---------------------------
bot.run(TOKEN)