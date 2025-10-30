from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import random
from typing import Any, Dict, List
from urllib.parse import quote_plus

from tinydb import Query, TinyDB

DICEBEAR_BASE_URL = "https://api.dicebear.com/9.x/bottts-neutral/png"
DICTIONARY_ID = "dictionary"


DEFAULT_ADJECTIVES: List[str] = [
    "かわいい","かっこいい","おもしろい","たのしい","やさしい","つよい","よわい","はやい","おそい","すばやい",
    "おおきい","ちいさい","ながい","みじかい","ひろい","せまい","あつい","さむい","あたたかい","すずしい",
    "あかい","あおい","しろい","くろい","きいろい","ちゃいろい","あおじろい","あかるい","くらい","あまい",
    "からい","にがい","すっぱい","しょっぱい","やわらかい","かたい","みずみずしい","うるさい","しぶい","するどい",
    "にぶい","たのもしい","こころづよい","あたらしい","ふるい","なつかしい","めずらしい","すごい","まるい","しかくい",
    "こい","うすい","かるい","おもい","けだかい","きびしい","おとなしい","すばらしい","たくましい","うれしい",
    "あざやかな","はなやかな","しずかな","にぎやかな","おだやかな","さわやかな","つやつやな","さらさらな","なめらかな","ふわふわな",
    "もふもふな","ぴかぴかな","きらきらな","じょうぶな","がんじょうな","しなやかな","優雅な","上品な","豪華な","素朴な",
    "無邪気な","純粋な","可憐な","温厚な","ほがらかな","気さくな","まじめな","正直な","大胆な","繊細な",
    "快適な","健やかな","清潔な","清らかな","陽気な","快活な","活発な","器用な","不器用な","几帳面な",
    "粋な","上質な","高級な","シンプルな","クールな","スマートな","エレガントな","キュートな","ワイルドな","ミステリアスな",
    "レトロな","モダンな","ポップな","カラフルな","カジュアルな","フレッシュな","フレンドリーな","ハッピーな","にこやかな","清楚な"
]


DEFAULT_NOUNS: List[str] = [
    "ねこ","いぬ","うさぎ","くま","ことり","とり","きつね","たぬき","りす","ねずみ",
    "ぞう","きりん","ぱんだ","らいおん","とら","おおかみ","くじら","いるか","さめ","ぺんぎん",
    "かめ","かえる","へび","あり","はち","ちょう","ほたる","かに","えび","いか",
    "たこ","くらげ","ひつじ","やぎ","うし","ぶた","うま","にわとり","ひよこ","すずめ",
    "ふくろう","はと","つばめ","かもめ","かも","おたまじゃくし","かぶとむし","くわがた","てんとうむし","花",
    "木","森","林","草","葉っぱ","つぼみ","実","種","根っこ","空",
    "雲","雨","雪","風","星","月","太陽","海","川","湖",
    "島","山","谷","砂","石","岩","砂利","土","氷","光",
    "影","音","声","音色","メロディ","リズム","ことば","えがお","なみだ","ゆめ",
    "きぼう","こころ","いのち","せかい","ぼうけん","ひみつ","まほう","でんせつ","おとぎ話","えほん",
    "ものがたり","うた","しあわせ","ゆうき","ちから","きずな","まなざし","ほほえみ","ごはん","パン",
    "ケーキ","クッキー","ドーナツ","アイス","チョコ","キャンディ","りんご","みかん","いちご","ぶどう",
    "もも","さくらんぼ","すいか","バナナ","なし","かき","メロン","かぼちゃ","じゃがいも","にんじん",
    "たまねぎ","トマト","きゅうり","なす","ピーマン","きのこ","おにぎり","うどん","そば","ラーメン",
    "カレー","ハンバーグ","ピザ","サンドイッチ","スープ","サラダ","おちゃ","こうちゃ","コーヒー","ジュース",
    "ミルク","ソーダ","みず","はちみつ","バター","チーズ","いえ","まち","みち","ばしょ",
    "お店","公園","学校","図書館","駅","空港","たび","ふね","くるま","でんしゃ",
    "バス","じてんしゃ","ひこうき","ロケット","エレベーター","はし","みなと","さかみち","まど","ドア",
    "かぎ","つくえ","いす","ベッド","ほん","ノート","えんぴつ","ペン","けしごむ","カバン",
    "ふでばこ","かさ","ふく","ぼうし","くつ","てぶくろ","マフラー","メガネ","時計","カメラ"
]



@dataclass(slots=True, frozen=True)
class BridgeProfile:
    seed: str
    display_name: str
    avatar_url: str


class BridgeProfileStore:
    """Manage adjective/noun dictionaries and provide random display profiles."""

    def __init__(self, db: TinyDB, table_name: str = "bridge_profiles") -> None:
        self._db = db
        self._table = db.table(table_name)
        self._query = Query()
        self._ensure_seed_data()

    def _ensure_seed_data(self) -> None:
        if self._table.contains(self._query.id == DICTIONARY_ID):
            return

        record = {
            "id": DICTIONARY_ID,
            "adjectives": DEFAULT_ADJECTIVES,
            "nouns": DEFAULT_NOUNS,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._table.insert(record)
        print("Bridge profile dictionary seeded with default adjectives and nouns.")

    def _load_dictionary(self) -> Dict[str, Any]:
        record = self._table.get(self._query.id == DICTIONARY_ID)
        if record is None:
            raise RuntimeError("Bridge profile dictionary is not initialized.")
        adjectives = record.get("adjectives") or []
        nouns = record.get("nouns") or []
        if not adjectives or not nouns:
            raise RuntimeError("Bridge profile dictionary is empty.")
        return {"adjectives": adjectives, "nouns": nouns}

    def get_profile(self, *, seed: str) -> BridgeProfile:
        dictionary = self._load_dictionary()
        rng = random.Random(seed)

        adjectives: List[str] = dictionary["adjectives"]
        nouns: List[str] = dictionary["nouns"]

        adjective = rng.choice(adjectives)
        noun = rng.choice(nouns)
        display_name = f"{adjective}{noun}"
        avatar_seed = f"{seed}-{adjective}-{noun}"
        avatar_url = f"{DICEBEAR_BASE_URL}?seed={quote_plus(avatar_seed)}"

        return BridgeProfile(
            seed=avatar_seed,
            display_name=display_name,
            avatar_url=avatar_url,
        )
