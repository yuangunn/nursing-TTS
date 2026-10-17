"""User-manageable phrase library.

Built-in phrase variants live in the template files.  Users can view, add,
edit, delete and reset them per element from the UI; edits are stored as
overrides in ``data_dir()/phrases.json`` and applied at generation time.

Key scheme (all strings):
    template  : "s1".."s5", or "_vitals" / "_global"
    field     : field key, or "intros" / "closings" (for templates),
                "bp" / "hr" / "rr" / "bt" / "spo2" / "lead" / "ending" (for _vitals)
    slot      : option value for select/multi options, or "phrases" / "none" / "false" for field-level lists

Additionally the *style expander* derives casual sentence endings from formal
ones ("~하였습니다." -> "~했고요," / "~했어요.") so every element has at least
three registers without writing each by hand.
"""
from __future__ import annotations

import json
import random
import re
import threading
from typing import Any

from .config import data_dir, load_settings

_LOCK = threading.Lock()
_CACHE: dict[str, Any] | None = None


def _path():
    return data_dir() / "phrases.json"


def _load() -> dict[str, Any]:
    global _CACHE
    if _CACHE is None:
        p = _path()
        try:
            _CACHE = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        except Exception:  # noqa: BLE001
            _CACHE = {}
    return _CACHE


def _save(data: dict[str, Any]) -> None:
    global _CACHE
    _CACHE = data
    _path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_override(template: str, field: str, slot: str) -> list[str] | None:
    return _load().get(template, {}).get(field, {}).get(slot)


def set_override(template: str, field: str, slot: str, phrases: list[str]) -> None:
    with _LOCK:
        data = _load()
        cleaned = [p.strip() for p in phrases if p and p.strip()]
        data.setdefault(template, {}).setdefault(field, {})[slot] = cleaned
        _save(data)


def reset_override(template: str, field: str | None = None, slot: str | None = None) -> None:
    with _LOCK:
        data = _load()
        if template not in data:
            return
        if field is None:
            data.pop(template, None)
        elif slot is None:
            data[template].pop(field, None)
        else:
            data[template].get(field, {}).pop(slot, None)
        _save(data)


def all_overrides() -> dict[str, Any]:
    return json.loads(json.dumps(_load()))


def import_overrides(data: dict[str, Any], replace: bool = False) -> int:
    with _LOCK:
        cur = {} if replace else _load()
        n = 0
        for t, fields in (data or {}).items():
            for f, slots in (fields or {}).items():
                for slot, phrases in (slots or {}).items():
                    if isinstance(phrases, list):
                        cur.setdefault(t, {}).setdefault(f, {})[slot] = [str(p) for p in phrases]
                        n += 1
        _save(cur)
        return n


def effective(template: str, field: str, slot: str, builtin: list[str]) -> list[str]:
    ov = get_override(template, field, slot)
    return list(ov) if ov is not None else list(builtin)


# ---------------------------------------------------------------------------
# Style expander: formal -> connective / casual endings
# ---------------------------------------------------------------------------

# (regex on the sentence end, connective form, casual polite form)
_END_RULES: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"하였습니다\.$"), "했고요,", "했어요."),
    (re.compile(r"하셨습니다\.$"), "하셨고요,", "하셨어요."),
    (re.compile(r"되었습니다\.$"), "됐고요,", "됐어요."),
    (re.compile(r"였습니다\.$"), "였고요,", "였어요."),
    (re.compile(r"했습니다\.$"), "했고요,", "했어요."),
    (re.compile(r"셨습니다\.$"), "셨고요,", "셨어요."),
    (re.compile(r"있습니다\.$"), "있고요,", "있어요."),
    (re.compile(r"없습니다\.$"), "없고요,", "없어요."),
    (re.compile(r"됩니다\.$"), "되고요,", "돼요."),
    (re.compile(r"합니다\.$"), "하고요,", "해요."),
    (re.compile(r"십니다\.$"), "시고요,", "세요."),
    (re.compile(r"갑니다\.$"), "가고요,", "가요."),
    (re.compile(r"옵니다\.$"), "오고요,", "와요."),
    (re.compile(r"듭니다\.$"), "들고요,", "들어요."),
    (re.compile(r"입니다\.$"), "이고요,", "@예요"),  # 예요/이에요 by batchim
]


def _batchim(ch: str) -> bool:
    code = ord(ch)
    return 0xAC00 <= code <= 0xD7A3 and (code - 0xAC00) % 28 != 0


_CHART_RULES: list[tuple[re.Pattern[str], str]] = [
    # requests to the next shift first (2026-10-17 대량 검수: "해주시면 되었음", "부탁드림")
    (re.compile(r"부탁드립니다\.$"), "요함."), (re.compile(r"\s?해\s?주세요\.$"), " 요함."),
    (re.compile(r"\s?해\s?주시면 (됩니다|돼요)\.$"), " 요함."),
    (re.compile(r"하였습니다\.$"), "함."), (re.compile(r"하셨습니다\.$"), "하심."), (re.compile(r"되었습니다\.$"), "됨."),
    (re.compile(r"됐습니다\.$"), "됨."),
    (re.compile(r"였습니다\.$"), "임."), (re.compile(r"했습니다\.$"), "함."), (re.compile(r"셨습니다\.$"), "심."),
    (re.compile(r"있습니다\.$"), "있음."), (re.compile(r"없습니다\.$"), "없음."), (re.compile(r"됩니다\.$"), "됨."),
    (re.compile(r"합니다\.$"), "함."), (re.compile(r"십니다\.$"), "심."), (re.compile(r"갑니다\.$"), "감."),
    (re.compile(r"옵니다\.$"), "옴."), (re.compile(r"듭니다\.$"), "듦."), (re.compile(r"입니다\.$"), "임."),
    (re.compile(r"고 있습니다\.$"), "고 있음."),
    # 2026-10-17 대량 검수: 기록체인데 "소변 맑습니다", "구토 1회 있었습니다", "격리 아닙니다"가 그대로 남았다
    (re.compile(r"(노랗|빨갛|하얗|파랗|까맣)습니다\.$"), "@color"),
    (re.compile(r"(럽|렵|겁|갑|깝|롭|쉽|덥|춥|맵|볍)습니다\.$"), "@b_irregular"),
]
_COLOR = {"노랗": "노란색임.", "빨갛": "빨간색임.", "하얗": "하얀색임.", "파랗": "파란색임.", "까맣": "까만색임."}
_B_IRREGULAR = {"럽": "러움.", "렵": "려움.", "겁": "거움.", "갑": "가움.", "깝": "까움.", "롭": "로움.", "쉽": "쉬움.", "덥": "더움.",
                "춥": "추움.", "맵": "매움.", "볍": "벼움."}


def _chart_sentence(p: str) -> str:
    for rx, rep in _CHART_RULES:
        m = rx.search(p)
        if not m:
            continue
        if rep == "@color":
            return p[: m.start()] + _COLOR[m.group(1)]
        if rep == "@b_irregular":
            return p[: m.start()] + _B_IRREGULAR[m.group(1)]
        return rx.sub(rep, p)
    m = re.search(r"([가-힣])습니다\.$", p)            # 맑습니다 → 맑음, 있었습니다 → 있었음, 들어갔습니다 → 들어갔음
    if m:
        return p[: m.start()] + m.group(1) + "음."
    m = re.search(r"([가-힣])니다\.$", p)              # 아닙니다 → 아님, 들립니다 → 들림 (받침 ㅂ → ㅁ)
    if m and (ord(m.group(1)) - 0xAC00) % 28 == 17:
        return p[: m.start()] + chr(ord(m.group(1)) - 1) + "."
    return p


def chart_form(phrase: str) -> str:
    """Nursing-chart register: '교육하였습니다.' -> '교육함.', '유지 중입니다.' -> '유지 중임.' — every sentence of the phrase."""
    parts = re.split(r"(?<=\.)\s+", phrase.strip())
    return " ".join(_chart_sentence(x) for x in parts)


_FROM_CHART: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"입원\.$"), "입원하셨습니다."), (re.compile(r"시작\.$"), "시작하셨습니다."), (re.compile(r"예정\.$"), "예정입니다."),
    (re.compile(r"투여\.$"), "투여 중입니다."), (re.compile(r"내원\.$"), "내원하셨습니다."), (re.compile(r"방문\.$"), "방문하셨습니다."),
    (re.compile(r"완료\.$"), "완료하였습니다."), (re.compile(r"추적\.$"), "추적 중입니다."), (re.compile(r"진행 중\.$"), "진행 중입니다."),
    (re.compile(r" 중\.$"), " 중입니다."), (re.compile(r"필요\.$"), "필요합니다."), (re.compile(r"호소\.$"), "호소하였습니다."), (re.compile(r"의심\.$"), "의심됩니다."),
    (re.compile(r"보냄\.$"), "보냈습니다."), (re.compile(r"계심\.$"), "계십니다."), (re.compile(r"하심\.$"), "하셨습니다."),
    (re.compile(r"(었|았|였|했|됐|웠|렸|켰|쳤|졌|셨)음\.$"), r"\1습니다."),   # 있었음 → 있었습니다, 하였음 → 하였습니다
    (re.compile(r"나옴\.$"), "나옵니다."), (re.compile(r"시범 보임\.$"), "시범 보였습니다."), (re.compile(r"보임\.$"), "보입니다."), (re.compile(r"들림\.$"), "들립니다."), (re.compile(r"들어감\.$"), "들어갑니다."),
    (re.compile(r"않음\.$"), "않습니다."), (re.compile(r"잠듦\.$"), "잠들었습니다."), (re.compile(r"낮춤\.$"), "낮췄습니다."),
    (re.compile(r"(?<=\s)둠\.$"), "두었습니다."), (re.compile(r"(?<=[려어와해\s])줌\.$"), "주었습니다."),
    (re.compile(r"(해|아|어|여)짐\.$"), r"\1집니다."), (re.compile(r"(넣|먹|씻|닦|찍|읽)음\.$"), r"\1습니다."),   # "손으로 밀어 넣음."
    (re.compile(r"(가능|필요|양호|깨끗|경미|불량|중요|심|동일|정상|적절)함\.$"), r"\1합니다."),   # state, not an action
    (re.compile(r"고 있음\.$"), "고 있습니다."), (re.compile(r"있음\.$"), "있습니다."),
    (re.compile(r"없음\.$"), "없습니다."), (re.compile(r"됨\.$"), "되었습니다."), (re.compile(r"(?<!포)함\.$"), "하였습니다."),
    (re.compile(r"임\.$"), "입니다."), (re.compile(r"(?<![오의관중안결])심\.$"), "셨습니다."),   # 오심(구역)·의심은 명사
]
# A chart clause inside a sentence ("잠들어 있음, 특이 호소 없음." / "식사량 확인함, 절반 정도 섭취함.") reads as a spoken
# connective; only the sentence end was converted before (2026-10-17 대량 검수: "잠들어 있음, 특이 호소 없습니다.").
_CLAUSE_FROM_CHART: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"있음, "), "있고, "), (re.compile(r"없음, "), "없고, "), (re.compile(r"않음, "), "않고, "),
    (re.compile(r"(드|내|무|계|하|으|보이)심, "), r"\1셨고, "),
    (re.compile(r"(?<!포)함, "), "했고, "), (re.compile(r"됨, "), "됐고, "), (re.compile(r"(?<![책모])임, "), "이고, "),
    (re.compile(r"(?<=\s)둠, "), "두었고, "), (re.compile(r"(?<=[려어와해\s])줌, "), "주었고, "), (re.compile(r"낮춤, "), "낮췄고, "),
    (re.compile(r"(해|아|어|여)짐, "), r"\1지고, "), (re.compile(r"들어감, "), "들어가고, "), (re.compile(r"나옴, "), "나오고, "),
]


_QUOTATIVE: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(가능|필요)함? (설명|교육)함"), r"\1하다고 \2함"), (re.compile(r"결정됨 (설명|교육)함"), r"결정된다고 \1함"), (re.compile(r"결정 (설명|교육)함"), r"결정한다고 \1함"),
    (re.compile(r"줄어듦 (설명|교육)함"), r"줄어든다고 \1함"), (re.compile(r"보냄 (설명|교육)함"), r"보낸다고 \1함"),
    (re.compile(r"됨 (설명|교육)함"), r"된다고 \1함"), (re.compile(r"있음 (설명|교육)함"), r"있다고 \1함"),
    (re.compile(r"없음 (설명|교육)함"), r"없다고 \1함"), (re.compile(r"예정 (설명|교육)함"), r"예정이라고 \1함"), (re.compile(r"금지 (설명|교육)함"), r"금지라고 \1함"),
]


def formal_from_chart(phrase: str) -> str:
    """'수면양상을 관찰함.' -> '수면양상을 관찰하였습니다.' (used for spoken styles)."""
    p = phrase.strip()
    for rx, rep in _QUOTATIVE:   # 2026-10-18 대량 검수: "통목욕은 … 두 달 뒤 가능 설명하였습니다"
        p = rx.sub(rep, p)
    for rx, rep in _CLAUSE_FROM_CHART:
        p = rx.sub(rep, p)
    for rx, rep in _FROM_CHART:
        if rx.search(p):
            return rx.sub(rep, p)
    return p


def expand_styles(phrase: str) -> list[str]:
    """Return [formal, connective, casual] variants of a formal phrase (deduplicated)."""
    p = formal_from_chart(phrase.strip())
    for rx, conn, casual in _END_RULES:
        m = rx.search(p)
        if not m:
            continue
        stem = p[: m.start()]
        if casual == "@예요":
            prev = stem.rstrip()[-1] if stem.rstrip() else ""
            unit = re.search(r"(kg|mg|cm|mm|cc|ml|mL|L|G|Fr|%)$", stem.rstrip())
            # digits/latin: decide by Korean reading of last char (digits mostly end with batchim except 2,4,5,9)
            if unit:   # read as the unit: 킬로그램·밀리그램 end in ㅁ, 센티미터·씨씨·퍼센트… in a vowel (2026-10-18: "57kg예요")
                b = unit.group(1) in ("kg", "mg")
            elif prev.isdigit():
                b = prev in "013678"
            elif _batchim(prev):
                b = True
            elif "가" <= prev <= "힣":
                b = False
            else:
                b = False
            casual_form = stem + ("이에요." if b else "예요.")
            conn = "이고요," if b else "고요,"   # "당뇨고요", not "당뇨이고요" (2026-10-18 2차 검수)
        else:
            casual_form = stem + casual
        return [p, stem + conn, casual_form]
    return [p]


# Ending variety inside one register (user 2026-10-17: "어투마다 어미가 3~5개는 있어야, 말도 안 되는 어미는 말고").
# Each rule only swaps one real ward ending for another of the same register and politeness.
_FORMAL_ALT: list[tuple[re.Pattern[str], list[str]]] = [
    (re.compile(r"설명하였습니다\.$"), ["설명드렸습니다.", "설명했습니다."]),
    (re.compile(r"교육하였습니다\.$"), ["교육했습니다.", "교육해 드렸습니다."]),
    (re.compile(r"안내하였습니다\.$"), ["안내드렸습니다.", "안내했습니다."]),
    (re.compile(r"확인하였습니다\.$"), ["확인했습니다."]),
    (re.compile(r"시행하였습니다\.$"), ["시행했습니다."]),
    (re.compile(r"하였습니다\.$"), ["했습니다."]),
    (re.compile(r"되었습니다\.$"), ["됐습니다."]),
]
_CHART_STATE = re.compile(r"(필요|요|가능|양호|깨끗|경미|불량|중요|동일|정상|적절|편안|면) ?(함|됨)\.$")
_CHART_ALT: list[tuple[re.Pattern[str], str]] = [(re.compile(r"함\.$"), "하였음."), (re.compile(r"됨\.$"), "되었음."), (re.compile(r"음\.$"), "음.")]


def vary_ending(text: str, rng: random.Random, register: str) -> str:
    """formal: 하였습니다 → 했습니다/드렸습니다 (40%), connective: 고요 → 구요 (40%), chart: 함 → 하였음 (30%)."""
    if register == "formal" and rng.random() < 0.4:
        for rx, alts in _FORMAL_ALT:
            if rx.search(text):
                return rx.sub(rng.choice(alts), text)
    elif register == "connective" and text.endswith("고요,") and rng.random() < 0.4:
        return text[:-3] + "구요,"
    elif register == "chart" and rng.random() < 0.3:
        if _CHART_STATE.search(text):    # "필요함/요함/…하시면 됨" are states, not past actions ("요하였음", "되었음")
            return text
        for rx, rep in _CHART_ALT:
            if rx.search(text):
                return rx.sub(rep, text)
    return text


def stylize(text: str, rng: random.Random, style: str = "mixed", allow_connective: bool = True,
            expand: bool | None = None) -> str:
    """Apply the style expander to an already-formatted sentence."""
    if expand is None:
        expand = bool(load_settings().get("auto_style_expand", True))
    if not expand or not text:
        return text
    if style == "chart":
        # 기록체: "~함/~됨/~임" on every sentence. Connectives stay as they are ("~하고,").
        return " ".join(vary_ending(x, rng, "chart") for x in re.split(r"(?<=\.)\s+", chart_form(text)))
    parts = re.split(r"(?<=\.)\s+", text.strip())
    if len(parts) > 1:   # multi-sentence 기록체 phrase: every sentence but the last here, the last one below (2026-10-17)
        text = " ".join([formal_from_chart(p) for p in parts[:-1]] + [parts[-1]])
    variants = expand_styles(text)
    if len(variants) == 1 and variants[0] != text:
        return variants[0]
    if len(variants) == 1:
        return text
    formal, conn, casual = variants
    formal, conn = vary_ending(formal, rng, "formal"), vary_ending(conn, rng, "connective")
    if style == "formal":
        conn = re.sub(r"(고요|구요),$", "고,", conn)      # 격식체 run-on: "~하였고," (user 2026-10-17: 어미가 제각각)
        options, weights = [formal, conn, casual], [9, 1, 0]
    elif style == "casual":
        options, weights = [formal, conn, casual], [2, 4, 4]
    else:
        options, weights = [formal, conn, casual], [5, 3, 2]
    if not allow_connective:
        weights[1] = 0
    if sum(weights) == 0:
        return formal
    return rng.choices(options, weights=weights)[0]


def pick(phrases: list[str], rng: random.Random, style: str = "mixed", expand: bool | None = None) -> str | None:
    """Choose a phrase and (optionally) a derived register.

    style: formal | casual | mixed.  ``expand`` defaults to the ``auto_style_expand`` setting.
    """
    if not phrases:
        return None
    if expand is None:
        expand = bool(load_settings().get("auto_style_expand", True))
    base = rng.choice(phrases)
    if not expand:
        return base
    variants = expand_styles(base)
    if len(variants) == 1:
        return base
    formal, conn, casual = variants
    if style == "formal":
        weights = [8, 1, 1]
    elif style == "casual":
        weights = [2, 4, 4]
    else:
        weights = [5, 3, 2]
    return rng.choices([formal, conn, casual], weights=weights)[0]
