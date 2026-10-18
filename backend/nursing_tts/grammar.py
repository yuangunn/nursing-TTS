"""Tiny Korean grammar helpers: sentence-final conversion and particle (조사) choice."""
from __future__ import annotations

import re

HANGUL_BASE = 0xAC00
JONG_COUNT = 28


def final_consonant(ch: str) -> int:
    """0 if no 받침, else jongseong index (1..27). ㄹ is 8."""
    code = ord(ch)
    if 0xAC00 <= code <= 0xD7A3:
        return (code - HANGUL_BASE) % JONG_COUNT
    return -1


_DIGIT_HANGUL = {"0": "영", "1": "일", "2": "이", "3": "삼", "4": "사", "5": "오", "6": "육", "7": "칠", "8": "팔", "9": "구"}
_LETTER_HANGUL = {"A": "이", "B": "비", "C": "씨", "D": "디", "E": "이", "F": "프", "G": "지", "H": "치", "I": "이",
                  "J": "이", "K": "이", "L": "엘", "M": "엠", "N": "엔", "O": "오", "P": "피", "Q": "큐", "R": "알",
                  "S": "스", "T": "티", "U": "유", "V": "이", "W": "유", "X": "스", "Y": "이", "Z": "트"}


def _last_sound(word: str) -> str | None:
    """Return the Hangul syllable that decides the particle for ``word``."""
    w = re.sub(r"[\s\)\]\"'%]+$", "", word)
    if not w:
        return None
    ch = w[-1]
    if 0xAC00 <= ord(ch) <= 0xD7A3:
        return ch
    if ch.isdigit():
        return _DIGIT_HANGUL[ch]
    if ch.isalpha():
        return _LETTER_HANGUL.get(ch.upper())
    return None


def has_batchim(word: str) -> bool | None:
    s = _last_sound(word)
    if s is None:
        return None
    return final_consonant(s) > 0


def ends_with_rieul(word: str) -> bool:
    s = _last_sound(word)
    return s is not None and final_consonant(s) == 8


_JOSA = {
    "(으)로": ("으로", "로"),
    "(이)가": ("이", "가"),
    "(은)는": ("은", "는"),
    "(을)를": ("을", "를"),
    "(과)와": ("과", "와"),
    "(이)랑": ("이랑", "랑"),
    "(아)야": ("아", "야"),
    "(이)었": ("이었", "였"),   # 호흡곤란이었다고 / 두드러기였다고
    "(이)": ("이", ""),
}
_JOSA_RE = re.compile(r"(\S+?)(" + "|".join(re.escape(k) for k in _JOSA) + r")")


def fix_josa(text: str) -> str:
    def repl(m: re.Match) -> str:
        word, marker = m.group(1), m.group(2)
        with_b, without_b = _JOSA[marker]
        b = has_batchim(word)
        if marker == "(으)로" and ends_with_rieul(word):
            return word + "로"
        if b is None:
            return word + without_b
        return word + (with_b if b else without_b)

    return _JOSA_RE.sub(repl, text)


# ---------------------------------------------------------------------------
# Connective -> sentence-final
# ---------------------------------------------------------------------------

_STEM_RULES = [
    (re.compile(r"(했|됐|였|셨|있|없|겠|았|었|갔|왔|받|봤|났|썼|줬|놨|뺐|켰|잤|섰|탔|샀|팠|좋|많|같|않)$"), "습니다"),
    (re.compile(r"아니$"), "@아닙니다"),
    (re.compile(r"이$"), "@입니다"),
    (re.compile(r"하$"), "@합니다"),
    (re.compile(r"되$"), "@됩니다"),
    (re.compile(r"시$"), "@십니다"),
    (re.compile(r"드리$"), "@드립니다"),
    (re.compile(r"주무시$"), "@주무십니다"),
    (re.compile(r"가$"), "@갑니다"),       # 잘 들어가고, -> 잘 들어갑니다.
    (re.compile(r"오$"), "@옵니다"),
]


def close_sentence(fragment: str) -> str:
    """'…교육했고,' -> '…교육했습니다.'  Falls back to a plain period."""
    frag = fragment.rstrip()
    if not frag.endswith(","):
        return frag
    stem = frag[:-1].rstrip()
    for ending in ("구요", "고요", "으며", "이며", "지만", "며", "고"):
        if stem.endswith(ending):
            stem = stem[: -len(ending)]
            break
    else:
        # "NRS 3점으로," / "저위험으로," -> "...입니다."
        for ending in ("으로", "로"):
            if stem.endswith(ending):
                return stem[: -len(ending)] + "입니다."
        return stem + "."
    if stem.endswith("(이)"):                       # "랩은 … 가능(이)구요," closes as "가능입니다." (2026-10-18: was "가능이.")
        return stem[:-3] + "입니다."
    if stem and final_consonant(stem[-1]) == 20:   # ㅆ 받침 = 과거·있다: 했/됐/드렸/낮췄/보냈 + 습니다
        return stem + "습니다."
    for rx, suffix in _STEM_RULES:
        if rx.search(stem):
            if suffix.startswith("@"):
                return rx.sub(suffix[1:], stem) + "."
            return stem + suffix + "."
    if re.search(r"(범위|상태|수준|정도|[\dA-Za-z%])$", stem):   # the copula went with "고": "정상 범위고," → "정상 범위입니다."
        return stem + "입니다."   # ponytail: word list; "모친 당뇨고," still closes as "…당뇨." — add nouns when they show up
    return stem + "."
