"""Recording-start signal: generation formats and a tolerant parser.

The mandatory spec form is
    「[연도]년 [월]월 [일]일 [시간]시 [분]분 [환자 성명] 님 [기록종류] 기록입니다.」
Real recordings also open with "환자명 강신자 간호정보조사하겠습니다" and the
like, so a trigger detector must accept the family of phrasings.  This module
(a) renders any of the known formats and (b) parses free text back into
date / time / name / kind / verb so generated and real signals can be labelled.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from . import korean

KINDS = ["간호정보조사", "퇴원간호", "수술전설명", "수술후설명", "인계", "경과기록"]

# Spoken aliases a nurse may use for each record kind (parser accepts all; generator
# uses them only when the "aliases" option is on).
KIND_ALIASES: dict[str, list[str]] = {
    "간호정보조사": ["간호정보조사", "간호정보조사지", "간호 정보 조사", "입원 간호정보조사", "간호정보 조사"],
    "퇴원간호": ["퇴원간호", "퇴원 간호", "퇴원간호기록", "퇴원 간호기록", "퇴원 교육", "퇴원교육", "퇴원간호기록지"],
    "수술전설명": ["수술전설명", "수술 전 설명", "수술전 설명", "수술 전 교육", "수술전 교육", "수술전 간호기록", "수술 전 간호기록", "시술전설명", "시술 전 설명"],
    "수술후설명": ["수술후설명", "수술 후 설명", "수술후 설명", "수술 후 교육", "수술후 교육", "수술후 간호기록", "수술 후 간호기록", "시술후설명", "시술 후 설명"],
    "인계": ["인계", "인수인계", "인계기록", "인수인계 기록", "근무 인계"],
    "경과기록": ["경과기록", "경과 기록", "시간별 경과기록", "간호 경과기록", "수술 후 경과기록", "수술후 경과기록", "항암 후 경과기록", "항암후 경과기록"],
    # S6 (2026-10-17): not a 수술후설명; S3-2 too from POD 1, named 수술 후 / 항암 후 경과기록 (user 2026-10-18)
}

# Written templates.  Placeholders: {date} {time} {name} {kind}
# Each entry: key, label, written, weight (for random mix)
FORMATS: list[dict[str, Any]] = [
    {"key": "strict", "label": "필수 형식: ○○○ 님 ○○ 기록입니다", "written": "{date} {time} {name} 님 {kind} 기록입니다.", "weight": 40},
    {"key": "label_do", "label": "환자명 ○○○ ○○하겠습니다", "written": "{date} {time} 환자명 {name} {kind}하겠습니다.", "weight": 15},
    {"key": "label_record", "label": "환자명 ○○○ ○○ 기록입니다", "written": "{date} {time} 환자명 {name} {kind} 기록입니다.", "weight": 10},
    {"key": "nim_do", "label": "○○○ 님 ○○하겠습니다", "written": "{date} {time} {name} 님 {kind}하겠습니다.", "weight": 8},
    {"key": "nim_start", "label": "○○○ 님 ○○ 시작합니다", "written": "{date} {time} {name} 님 {kind} 시작합니다.", "weight": 8},
    {"key": "nim_record_start", "label": "○○○ 님 ○○ 기록 시작하겠습니다", "written": "{date} {time} {name} 님 {kind} 기록 시작하겠습니다.", "weight": 7},
    {"key": "patient_record", "label": "○○○ 환자 ○○ 기록입니다", "written": "{date} {time} {name} 환자 {kind} 기록입니다.", "weight": 6},
    {"key": "label_start", "label": "환자명 ○○○, ○○ 시작하겠습니다", "written": "{date} {time} 환자명 {name}, {kind} 시작하겠습니다.", "weight": 6},
]
FORMAT_KEYS = [f["key"] for f in FORMATS]


def builtin_written_templates() -> list[str]:
    return [f["written"] for f in FORMATS]


def _kind_text(kind: str, rng: random.Random, use_aliases: bool) -> str:
    if use_aliases and rng.random() < 0.35:
        return rng.choice(KIND_ALIASES.get(kind, [kind]))
    return kind


def render(when: datetime, name: str, kind: str, fmt: str = "strict", rng: random.Random | None = None,
           use_aliases: bool = False, templates: list[str] | None = None) -> tuple[str, str, str]:
    """Return (written, tts, format_key).

    ``fmt`` is a format key, "random" (weighted mix of all known templates), or a
    literal template containing {name}.  ``templates`` (from the phrase store) may
    extend/replace the built-in list for "random".
    """
    rng = rng or random.Random()
    pool = templates if templates else builtin_written_templates()
    if fmt == "random":
        if templates:
            written_t = rng.choice(pool)
        else:
            written_t = rng.choices([f["written"] for f in FORMATS], weights=[f["weight"] for f in FORMATS])[0]
    elif "{name}" in fmt:
        written_t = fmt
    else:
        f = next((f for f in FORMATS if f["key"] == fmt), FORMATS[0])
        written_t = f["written"]
    kind_text = _kind_text(kind, rng, use_aliases)
    if kind_text.endswith("기록") and "{kind} 기록" in written_t:
        kind_text = kind_text[:-2].strip()            # "경과기록 기록입니다" → "경과 기록입니다"
    date_w = korean.written_date(when.year, when.month, when.day)
    time_w = korean.written_time(when.hour, when.minute)
    date_t = korean.read_date(when.year, when.month, when.day)
    time_t = korean.read_time(when.hour, when.minute)
    written = written_t.format(date=date_w, time=time_w, name=name, kind=kind_text)
    tts = written_t.format(date=date_t, time=time_t, name=name, kind=kind_text)
    key = next((f["key"] for f in FORMATS if f["written"] == written_t), "custom")
    return written, tts, key


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

@dataclass
class SignalMatch:
    ok: bool
    text: str = ""
    start: int = 0
    end: int = 0
    year: int | None = None
    month: int | None = None
    day: int | None = None
    hour: int | None = None
    minute: int | None = None
    name: str = ""
    kind: str = ""
    kind_text: str = ""
    verb: str = ""
    format: str = ""
    missing: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        d = self.__dict__.copy()
        d["datetime"] = (f"{self.year:04d}-{self.month:02d}-{self.day:02d}T{self.hour:02d}:{self.minute:02d}"
                         if None not in (self.year, self.month, self.day, self.hour, self.minute) else None)
        return d


_ALL_KIND_ALIASES = sorted({a for v in KIND_ALIASES.values() for a in v}, key=len, reverse=True)
_KIND_RE = "|".join(re.escape(a) for a in _ALL_KIND_ALIASES)
_DATE_RE = re.compile(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일")
_TIME_RE = re.compile(r"(오전|오후|아침|저녁|새벽|낮|밤)?\s*(\d{1,2})\s*시(?:\s*(\d{1,2})\s*분|\s*반)?")
_NAME_RE = re.compile(
    r"(?:환자\s*명|환자\s*이름|환자|성명)?\s*[:,]?\s*([가-힣]{2,4})\s*(?:님|환자분|환자|씨)?"
)
_VERB_RE = re.compile(
    r"(기록\s*시작\s*하겠습니다|기록\s*시작합니다|시작\s*하겠습니다|시작합니다|시작할게요|하겠습니다|할게요|기록입니다|기록이에요|입니다|이에요|예요|입니다요)"
)
_NON_NAME = {"환자", "환자명", "성명", "오전", "오후", "기록", "간호", "시작", "입니다", "님", "분", "시", "오늘", "이상"}


def parse(text: str) -> SignalMatch:
    """Find a recording signal anywhere in ``text`` (usually its first line)."""
    head = text.strip().split("\n")[0] if text else ""
    window = text[: max(len(head) + 1, 200)]
    m_date = _DATE_RE.search(window)
    m_kind = re.search(_KIND_RE, window)
    if not m_kind:
        return SignalMatch(ok=False, missing=["kind"] + (["date"] if not m_date else []))
    start = m_date.start() if m_date else 0
    m_time = _TIME_RE.search(window, m_date.end() if m_date else 0)
    hour = minute = None
    if m_time:
        hour = int(m_time.group(2))
        minute = int(m_time.group(3)) if m_time.group(3) else (30 if m_time.group(0).rstrip().endswith("반") else 0)
        ampm = m_time.group(1)
        if ampm in ("오후", "저녁", "밤") and hour < 12:
            hour += 12
        elif ampm in ("오전", "아침", "새벽") and hour == 12:
            hour = 0
    # name: between the time (or date) and the kind
    seg_start = m_time.end() if m_time else (m_date.end() if m_date else 0)
    seg = window[seg_start: m_kind.start()]
    name = ""
    for cand in re.finditer(r"[가-힣]{2,4}", seg):
        w = cand.group(0)
        if w in _NON_NAME or w.endswith("환자명"):
            continue
        # strip trailing honorific glued to the name ("강신자님")
        w = re.sub(r"(님|씨)$", "", w) if len(w) > 2 else w
        if w and w not in _NON_NAME:
            name = w
            break
    kind_text = m_kind.group(0)
    kind = next((k for k, aliases in KIND_ALIASES.items() if kind_text in aliases), "")
    m_verb = _VERB_RE.search(window, m_kind.end())
    verb = m_verb.group(1) if m_verb else ""
    end = (m_verb.end() if m_verb else m_kind.end())
    # extend to sentence end
    m_end = re.search(r"[.!?]", window[end:])
    if m_end and m_end.start() < 4:
        end += m_end.end()
    missing = [k for k, v in (("date", m_date), ("time", m_time), ("name", name), ("verb", verb)) if not v]
    fmt = _guess_format(window[start:end])
    return SignalMatch(
        ok=bool(m_date and m_time and name), text=window[start:end].strip(), start=start, end=end,
        year=int(m_date.group(1)) if m_date else None, month=int(m_date.group(2)) if m_date else None,
        day=int(m_date.group(3)) if m_date else None, hour=hour, minute=minute, name=name, kind=kind,
        kind_text=kind_text, verb=verb, format=fmt, missing=missing or None,
    )


def _guess_format(s: str) -> str:
    s2 = re.sub(r"\s+", " ", s)
    if "환자명" in s2 and "하겠습니다" in s2 and "시작" not in s2:
        return "label_do"
    if "환자명" in s2 and "기록입니다" in s2:
        return "label_record"
    if "환자명" in s2 and "시작" in s2:
        return "label_start"
    if "님" in s2 and "기록 시작" in s2:
        return "nim_record_start"
    if "님" in s2 and "시작합니다" in s2:
        return "nim_start"
    if "님" in s2 and "하겠습니다" in s2:
        return "nim_do"
    if "환자" in s2 and "기록입니다" in s2 and "님" not in s2:
        return "patient_record"
    if "님" in s2 and "기록입니다" in s2:
        return "strict"
    return "custom"
