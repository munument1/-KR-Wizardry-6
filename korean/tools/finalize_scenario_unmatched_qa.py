#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ITEMS = ROOT / "korean/translation/scenario_items_ko.csv"
ACTORS = ROOT / "korean/translation/scenario_monsters_ko.csv"
REVIEW = ROOT / "korean/translation/scenario_unmatched_review_2026-09-01.json"

# Only rows that had no legacy W7 match are changed here. Matched rows stay on the
# imported legacy translation unless a later dedicated QA pass changes them.
ITEM_CORRECTIONS = {
    28: "곤봉",
    61: "강타의검",
    63: "흑검",
    67: "머스터드메이스",
    71: "한밤의합창",
    78: "뼈분쇄기",
    82: "레이딩검",
    89: "프로메테우스뿔",
    90: "바소리라",
    98: "뻐꾸기울음",
    100: "램의단검",
    105: "올리비아에스톡",
    151: "호액시얼판금",
    174: "회백각반",
    178: "기름진장갑",
    197: "납장화",
    203: "카메일바지",
    208: "마법로브상",
    209: "마법로브하",
    210: "베널로브상",
    211: "베널로브하",
    227: "모르드카이고깔",
    228: "오비투스투구",
    229: "성스런슬리퍼",
    231: "유리구두",
    233: "하이젠망토",
    240: "안대",
    244: "절망의사슬",
    256: "죽음멤포",
    268: "스라소니반지",
    269: "두꺼비돌반지",
    270: "정신의반지",
    272: "속도의반지",
    273: "손재주반지",
    274: "밤의부적",
    275: "공기의부적",
    276: "바람의부적",
    277: "얼음의부적",
    281: "기적의앙크",
    282: "순수의앙크",
    286: "파이레앙크",
    287: "만트라의책",
    288: "환희의책",
    290: "시집",
    291: "아르니앙크",
    293: "마기쿠스지팡이",
    294: "별의지팡이",
    295: "드리아드지팡이",
    296: "달의지팡이",
    297: "마녀지팡이",
    298: "파멸지팡이",
    299: "신비완드",
    300: "직조완드",
    302: "유령완드",
    303: "사령술막대",
    304: "파괴완드",
    310: "픽시막대",
    312: "밤의막대",
    349: "소환술",
    353: "부양의책",
    354: "과부의책",
    355: "감정의책",
    356: "평온의책",
    357: "항마법책",
    360: "실명",
    361: "고대가루",
    362: "신비가루",
    363: "얼음방패책",
    365: "공기방패책",
    366: "침묵의책",
    368: "방향의책",
    370: "냉기의책",
    371: "실명의책",
    372: "약화의책",
    373: "둔화의책",
    374: "독의책",
    375: "화염방패책",
    376: "보호의책",
    377: "경상치료책",
    378: "수면의책",
    379: "갑옷용해책",
    383: "미사일지팡이",
    384: "스페이드열쇠",
    386: "램열쇠",
    395: "망자기록",
    397: "밧줄&갈고리",
    400: "JR해독기",
    402: "신비한기름",
    403: "티켓조각",
    404: "램의책",
    407: "고무가닥",
    408: "고무땋은줄",
    410: "거대바위",
    411: "장신구꾸러미",
    418: "영혼의뿔",
    423: "모래주머니",
    426: "발가루",
    428: "미노스열쇠",
    429: "저주열쇠",
    430: "저주의책",
    431: "재의원통",
    432: "재의원통",
    434: "사이렌의책",
    435: "재의원통",
    436: "길잃은자열쇠",
    438: "물담뱃대",
    443: "편지병",
    448: "갈고리낚싯줄",
    450: "망자열쇠",
    453: "드로우열쇠",
    454: "기사열쇠",
    455: "발키리열쇠",
    456: "여왕열쇠",
    457: "악의열쇠",
    458: "성스런나무말뚝",
    459: "강화성수",
    460: "아람의지팡이",
    462: "반사의돌",
    463: "결정의열쇠",
    464: "첫시험열쇠",
    465: "난제의열쇠",
    466: "첫시험열쇠",
    467: "무의열쇠",
    468: "최후의열쇠",
    469: "최후의열쇠",
    471: "별의열쇠",
    477: "마법쿠키",
    478: "약초패티",
    481: "델파이반지",
}

MONSTER_NAME_CORRECTIONS = {
    5: "기는덩굴",
    6: "연기덩굴",
    7: "조임덩굴",
    19: "광폭쥐",
    20: "밀림덩굴",
    23: "슬라임",
    24: "독슬라임",
    25: "히드라식물",
    26: "던전거머리",
    28: "부패시체",
    31: "뚱뚱한쥐",
    34: "아멘투트버트",
    38: "여주술사",
    42: "젤리구름",
    43: "젤라틴안개",
    45: "맨오워",
    47: "채집개미",
    48: "바스페스",
    49: "산성슬라임",
    50: "냉기슬라임",
    51: "거대웜",
    52: "백색웜",
    54: "파이레파라오",
    58: "언덕거인",
    60: "산악거인",
    64: "통행세트롤",
    69: "악마헬캣",
    70: "구프글루프",
    82: "타란툴라",
    84: "맨오워",
    88: "사이렌마법사",
    92: "나이트건트",
    100: "스펙터",
    104: "좀비경비병",
    105: "남빛박쥐",
    106: "괴물뱀",
    117: "디스코좀비",
    118: "유령마녀",
    119: "광기해골",
    121: "흑기사",
    125: "암흑성전사",
    138: "푸른꼬리파리",
    140: "다이쇼달인",
    142: "원혼",
    144: "암살자",
    145: "중닌",
    149: "그렘린",
    151: "드라큘라",
    163: "다이묘",
    164: "대사부",
    166: "럼블바위",
    167: "램의사제",
    168: "피트핀드",
    169: "하급데빌",
    171: "화염헬캣",
    175: "뒤틀린실프",
    200: "에테르박쥐",
    201: "유사드래곤",
    204: "헬리온",
    208: "셰이드",
    213: "늑대쥐",
    215: "놀트롤",
    216: "파이로에이어",
    219: "그림자",
    223: "환영체",
}

# Korean does not need English-style plural inflection, so singular/plural share
# the same Korean label. Short labels preserve the original generic identity.
MONSTER_SHORT = {
    0:"쥐",1:"쥐",2:"박쥐",3:"박쥐",4:"박쥐",5:"덩굴",6:"덩굴",7:"덩굴",
    8:"도적",9:"도적",10:"도적",11:"거대뱀",12:"악취시체",13:"박쥐",14:"도적",15:"도적",16:"도적",
    18:"쥐",19:"쥐",20:"덩굴",23:"슬라임",24:"슬라임",25:"히드라식물",26:"거대웜",28:"부패시체",
    29:"부패시체",30:"메이티선장",31:"뚱뚱한쥐",32:"퀴퀘그",34:"아멘투트버트",35:"르몽테스",
    36:"원주민",37:"원주민",38:"원주민",39:"원주민",40:"아마줄루여왕",41:"부패시체",42:"구름",43:"구름",
    44:"구름",45:"구름",46:"거대개미",47:"거대개미",48:"거대개미",49:"슬라임",50:"슬라임",51:"거대웜",
    52:"거대웜",53:"고무괴물",54:"언데드파라오",55:"드워프",56:"드워프",57:"수상한자",58:"거인",59:"거인",
    60:"거인",61:"바위수호자",62:"마우무무",63:"스미티",64:"통행세트롤",65:"괴물박쥐",66:"미스타파파스",
    67:"프리츠그린스",68:"클라우스그린스",69:"악마헬캣",70:"구프글루프",71:"쿠왈리쿠보나",72:"쿠왈리쿠보나",
    73:"아마줄루여왕",74:"바다뱀",75:"바다뱀",77:"거대게",78:"거대게",79:"비행곤충",80:"비행곤충",
    81:"거대거미",82:"거대거미",83:"물젤라틴",84:"물젤라틴",86:"미노데몬",87:"사이렌",88:"사이렌",
    90:"사이렌",91:"카론",92:"악마 형상",95:"해골",96:"해골",99:"유령",100:"유령",101:"그림자",
    102:"그림자",104:"좀비경비병",105:"검은박쥐",106:"괴물뱀",107:"뱀",108:"에일라유령",109:"마로유령",
    110:"불리유령",111:"나르시유령",113:"거인",114:"마이라이",115:"애벌레",116:"보크",117:"디스코좀비",
    118:"유령마녀",119:"광기해골",120:"로빈윈드마른",121:"흑기사",122:"브리거드볼탄",123:"하야토다이쿠타",
    124:"하이랜더",125:"암흑성전사",126:"발키리",127:"사무라이",128:"재앙왕",129:"쥐",130:"램수호자",
    132:"죽음기사",134:"닌자",135:"궁수",136:"뱀인간",138:"비행곤충",140:"사무라이",141:"로브형상",
    142:"그림자",144:"닌자",145:"닌자",146:"고블린",147:"고블린",148:"고블린",149:"고블린",
    150:"조르피투스",151:"드라큘라",152:"레베카",153:"* 벨 라 *",154:"거대도마뱀",155:"페어리여왕",
    156:"페어리",157:"반딧불",158:"기괴한마법사",159:"기괴한마법사",160:"기사",161:"상급 악마",
    162:"악마 형상",163:"사무라이",164:"닌자",165:"언데드파라오",166:"거대바위머리",167:"염소머리인간",
    168:"지옥악마",169:"악마 형상",170:"그림자",171:"헬캣",173:"거인",174:"상급 악마",175:"페어리",
    176:"암흑성전사",177:"으스스한형상",178:"언데드파라오",179:"괴물뱀",180:"뱀",200:"에테르박쥐",
    201:"유사드래곤",202:"가고일",203:"버발랑",204:"헬리온",205:"상급 악마",206:"해골",207:"좀비",
    208:"셰이드",209:"언데드군주",210:"아리엘시종",211:"상급 악마",212:"독덩굴",213:"늑대쥐",
    214:"픽시",215:"놀트롤",216:"파이로에이어",217:"호라스무스",218:"환영",219:"그림자",220:"괴이체",
    221:"키메라",222:"망령",223:"환영체",
}

NPC_CORRECTIONS = {
    4: "통행세트롤",
    8: "사제유령",
    15: "유령형상",
}

VARIANT_ORDER = {"name": 0, "name_plural": 1, "short_name": 2, "short_name_plural": 3}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["category", "record_index", "variant", "translation"])
        w.writeheader()
        w.writerows(rows)


def encoded_len(text: str) -> int:
    # Runtime Korean text uses two bytes per Hangul/custom glyph and one byte per ASCII.
    return sum(1 if ord(ch) < 0x80 else 2 for ch in text)


def main() -> None:
    item_rows = read_csv(ITEMS)
    before_items = {int(r["record_index"]): r["translation"] for r in item_rows}
    assert len(item_rows) == 452
    for row in item_rows:
        idx = int(row["record_index"])
        if idx in ITEM_CORRECTIONS:
            row["translation"] = ITEM_CORRECTIONS[idx]
        if encoded_len(row["translation"]) > 15:
            raise ValueError(f"item {idx} exceeds 15-byte payload: {row['translation']}")
    write_csv(ITEMS, item_rows)

    actor_rows = read_csv(ACTORS)
    monster_names = {int(r["record_index"]): r["translation"] for r in actor_rows if r["category"] == "monster" and r["variant"] == "name"}
    npc_names = {int(r["record_index"]): r["translation"] for r in actor_rows if r["category"] == "npc" and r["variant"] == "name"}
    assert len(monster_names) == 186
    assert len(npc_names) == 30

    for idx, value in MONSTER_NAME_CORRECTIONS.items():
        if idx not in monster_names:
            raise KeyError(f"unknown monster {idx}")
        monster_names[idx] = value
    for idx, value in NPC_CORRECTIONS.items():
        npc_names[idx] = value

    normal_monsters = sorted(idx for idx in monster_names if idx != 250)
    assert len(normal_monsters) == 185
    assert set(normal_monsters) == set(MONSTER_SHORT), (set(normal_monsters) - set(MONSTER_SHORT), set(MONSTER_SHORT) - set(normal_monsters))

    out: list[dict[str, str]] = []
    for idx in sorted(monster_names):
        name = monster_names[idx]
        variants = [("name", name)]
        if idx != 250:
            short = MONSTER_SHORT[idx]
            variants += [("name_plural", name), ("short_name", short), ("short_name_plural", short)]
        for variant, trans in variants:
            if encoded_len(trans) > 15:
                raise ValueError(f"monster {idx}/{variant} exceeds 15-byte payload: {trans}")
            out.append({"category": "monster", "record_index": str(idx), "variant": variant, "translation": trans})
    for idx in sorted(npc_names):
        trans = npc_names[idx]
        if encoded_len(trans) > 15:
            raise ValueError(f"npc {idx} exceeds 15-byte payload: {trans}")
        out.append({"category": "npc", "record_index": str(idx), "variant": "name", "translation": trans})
    out.sort(key=lambda r: (0 if r["category"] == "monster" else 1, int(r["record_index"]), VARIANT_ORDER[r["variant"]]))
    assert len(out) == 771
    write_csv(ACTORS, out)

    changed_items = {str(i): {"before": before_items[i], "after": ITEM_CORRECTIONS[i]} for i in sorted(ITEM_CORRECTIONS) if before_items.get(i) != ITEM_CORRECTIONS[i]}
    report = {
        "date": "2026-09-01",
        "policy": "legacy-matched rows remain legacy-first; all previously unmatched Scenario rows manually reviewed against W6 source names and canonical item/monster references",
        "field_counts": {"items": 452, "monster_fields": 741, "npc_names": 30, "total": 1223},
        "legacy_matched_fields": 277,
        "previously_unmatched_fields_reviewed": 946,
        "explicit_rows_after_qa": 1223,
        "item_corrections": changed_items,
        "monster_name_corrections": {str(k): v for k, v in sorted(MONSTER_NAME_CORRECTIONS.items())},
        "npc_corrections": {str(k): v for k, v in sorted(NPC_CORRECTIONS.items())},
        "plural_policy": "Korean singular/plural labels are identical; English plural fields are explicitly populated with the reviewed Korean singular label.",
        "short_name_policy": "All 185 short-name pairs are explicitly populated from the original generic monster identity instead of falling back to the full monster name.",
        "runtime_field_limit": "all output labels <= 15 encoded payload bytes",
    }
    REVIEW.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "item_rows": len(item_rows),
        "actor_rows": len(out),
        "scenario_rows": len(item_rows) + len(out),
        "item_corrections": len(changed_items),
        "monster_name_corrections": len(MONSTER_NAME_CORRECTIONS),
        "npc_corrections": len(NPC_CORRECTIONS),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
