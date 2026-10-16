"""대화형 간호정보조사 (user 2026-10-17): the nurse asks (~까요? / ~세요?), the patient answers (~어요. / 네. / 아니오.),
and a patient of 80 or older answers in 반말 (~어. / 응. / 아니.).

Only the admission interview (S1) has a dialogue form: the chart facts the nurse reads (route, complaint, vitals,
risk scores, nursing problems) stay nurse narration; the items a nurse actually *asks* become question/answer
turns built from the same form values, so the dialogue never contradicts the narrated chart.
"""
from __future__ import annotations

import random
import re
from typing import Any, Callable

from .generator import Patient
from .grammar import fix_josa

BANMAL_AGE = 80

# fields whose content the patient already says in an answer: not narrated again by the nurse
SKIP_IN_DIALOGUE = {"history_detail", "allergy_reaction", "medications", "supplements", "weight_screen", "intake_screen",
                    "sleep_screen", "depression_screen", "adl", "weakness_note", "symptom_note", "intake_note", "pain_site", "pain_char"}

ACKS = ["네.", "네, 알겠습니다.", "아, 네.", "네, 그러시군요."]

_LAY_HISTORY = {"htn": "고혈압", "dm": "당뇨", "heart": "심장병", "stroke": "뇌졸중", "lung": "폐 질환", "ckd": "신장병", "liver": "간 질환",
                "thyroid": "갑상선", "tb": "결핵", "prediabetes": "당뇨 전단계", "dyslipidemia": "고지혈증", "hypothyroid": "갑상선 기능 저하"}
_LAY_MEDS = {"htn": "혈압약", "dm": "당뇨약", "heart": "심장약", "stroke": "피 묽게 하는 약", "lung": "흡입기", "ckd": "신장약", "liver": "간약",
             "thyroid": "갑상선약", "hypothyroid": "갑상선약", "dyslipidemia": "고지혈증약", "prediabetes": "", "tb": ""}
_LAY_SURGERY = [("충수절제술", "맹장 수술"), ("제왕절개", "제왕절개"), ("담낭절제술", "담낭 수술"), ("백내장 수술", "백내장 수술"),
                ("편도절제술", "편도 수술"), ("유방 수술", "유방 수술"), ("대장 수술", "대장 수술")]
_LAY_SITE = [("고관절", "엉덩이 쪽"), ("무릎 아래", "정강이"), ("무릎", "무릎"), ("어깨", "어깨"), ("발목", "발목"), ("손목", "손목"), ("쇄골", "쇄골 쪽"),
             ("우상복부", "오른쪽 윗배"), ("하복부", "아랫배"), ("복부", "배"), ("유방", "가슴"), ("항문", "항문"), ("서혜부", "사타구니"),
             ("옆구리", "옆구리"), ("목", "목"), ("코 주위", "코 주위"), ("발", "발"), ("수술 부위", "수술한 데")]
_LAY_CHAR = {"dull": "뻐근하게", "sharp": "찌르듯이", "colicky": "쥐어짜듯이", "tender": "누르면", "movement": "움직이면 더"}
_LAY_SYMPTOM = {"식후 더부룩함": "밥 먹으면 더부룩해요.", "다리 부종": "다리가 좀 부어요.", "가끔 두근거림": "가끔 가슴이 두근거려요.", "계단 오를 때 숨참": "계단 오르면 숨이 차요."}
_LAY_FAMILY = {"부친": "아버지가", "모친": "어머니가", "형제": "형제가", "자매": "자매가"}


def _join(nouns: list[str]) -> str:
    nouns = [n for n in nouns if n]
    if not nouns:
        return ""
    if len(nouns) == 1:
        return nouns[0]
    return "(이)랑 ".join(nouns[:-1]) + "(이)랑 " + nouns[-1] if len(nouns) <= 3 else ", ".join(nouns)   # 당뇨랑 고혈압이랑 (fix_josa)


def to_banmal(text: str) -> str:
    """존댓말 patient answer -> 반말 (80세 이상). Only real endings: 어요→어, 아요→아, 해요→해, 예요→야, 이에요→이야, 네→응, 아니오→아니."""
    out = []
    for sent in re.split(r"(?<=[.!?])\s+", text.strip()):
        s = sent
        s = re.sub(r"^네[,.]\s*", "응, ", s) if re.match(r"^네[,.]", s) else s
        s = re.sub(r"^(아니오|아니요)[,.]?\s*", "아니, ", s)
        s = re.sub(r"이에요([.?!])$", r"이야\1", s)
        s = re.sub(r"예요([.?!])$", r"야\1", s)
        s = re.sub(r"(죠|지요)([.?!])$", r"지\2", s)
        s = re.sub(r"(세요)([.?!])$", r"\2", s)
        s = re.sub(r"요([.?!])$", r"\1", s)
        s = s.replace("응, .", "응.").replace("아니, .", "아니.")
        if s.endswith(", "):
            s = s[:-2] + "."
        out.append(s)
    return " ".join(x for x in out if x)


def _answer(text: str, patient: Patient) -> str:
    text = fix_josa(text)
    return to_banmal(text) if (patient.age or 0) >= BANMAL_AGE else text


# --- answer builders: (form, patient, rng) -> polite answer text ----------------------------------------------
def _a_history(f: dict[str, Any], p: Patient, rng: random.Random) -> str:
    hist = [h for h in (f.get("history") or []) if h in _LAY_HISTORY]
    if not hist:
        return rng.choice(["아니오, 없어요.", "특별히 없어요.", "없어요."])
    return f"네, {_join([_LAY_HISTORY[h] for h in hist])} 있어요."


def _a_meds(f: dict[str, Any], p: Patient, rng: random.Random) -> str:
    hist = [h for h in (f.get("history") or []) if h in _LAY_MEDS]
    meds = [_LAY_MEDS[h] for h in hist if _LAY_MEDS[h]]
    if "인슐린" in str(f.get("medications") or ""):
        meds = [m for m in meds if m != "당뇨약"] + ["인슐린"]
    if not meds:
        return rng.choice(["따로 먹는 약은 없어요.", "없어요."])
    if "인슐린" in meds:
        rest = [m for m in meds if m != "인슐린"]
        return (f"네, {_join(rest)} 먹고 " if rest else "네, ") + "당뇨는 인슐린 맞아요."
    return rng.choice([f"네, {_join(meds)} 먹고 있어요.", f"{_join(meds)} 아침에 먹어요."])


def _a_antiplatelet(f: dict[str, Any], p: Patient, rng: random.Random) -> str | None:
    v = f.get("antiplatelet")
    if v == "stopped":
        return rng.choice(["네, 일주일 전부터 안 먹었어요.", "네, 끊고 왔어요."])
    if v == "taking":
        return "아직 먹고 있어요."
    return None


def _a_past_surgery(f: dict[str, Any], p: Patient, rng: random.Random) -> str:
    raw = str(f.get("past_surgery") or "")
    if not raw or raw == "없음":
        return rng.choice(["아니오, 없어요.", "수술은 처음이에요."])
    lay = next((l for k, l in _LAY_SURGERY if k in raw), raw)
    m = re.match(r"(\d+)(년|개월) 전", raw)
    when = f"{m.group(1)}{m.group(2)} 전에" if m else "어릴 때" if "어릴 때" in raw else "전에"
    return f"네, {when} {lay} 했어요."


def _a_transfusion(f: dict[str, Any], p: Patient, rng: random.Random) -> str:
    return {"yes": "네, 전에 한 번 받았어요.", "yes_reaction": "네, 받고 두드러기 났던 적 있어요."}.get(str(f.get("transfusion")), "없어요.")


def _a_allergy(f: dict[str, Any], p: Patient, rng: random.Random) -> str:
    al = [a for a in (f.get("allergy") or []) if a != "none"]
    if not al:
        return rng.choice(["없어요.", "아니오, 없어요.", "특별히 없어요."])
    reaction = str(f.get("allergy_reaction") or "두드러기")
    a = al[0]
    if a == "food":
        return f"{str(f.get('intake_note') or '해산물').replace(' 알레르기', '')} 먹으면 {reaction} 나요."
    return {"contrast": "조영제 맞고 안 좋았던 적 있어요.", "penicillin": f"페니실린 맞으면 {reaction} 나요.", "nsaid": f"진통제 먹으면 {reaction} 나요.",
            "antibiotic": f"항생제에 {reaction} 난 적 있어요."}.get(a, "네, 좀 있어요.")


def _a_supplements(f: dict[str, Any], p: Patient, rng: random.Random) -> str:
    v = str(f.get("supplements") or "")
    return f"{v} 먹어요." if v and v != "없음" else "없어요."


def _a_family(f: dict[str, Any], p: Patient, rng: random.Random) -> str:
    v = str(f.get("family_history") or "")
    if f.get("family_none") or not v or v == "없음":
        return rng.choice(["없어요.", "특별히 없어요."])
    m = re.match(r"(부친|모친|형제|자매)\s+(.+)", v)
    return f"{_LAY_FAMILY[m.group(1)]} {m.group(2)} 있으셨어요." if m else f"{v} 있어요."


def _a_emotion(f: dict[str, Any], p: Patient, rng: random.Random) -> str:
    em = f.get("emotion") or []
    if "anxiety" in em:
        return rng.choice(["네, 좀 걱정돼요.", "많이 긴장되네요."])
    if "depression" in em:
        return "요즘 기분이 좀 가라앉아요."
    return rng.choice(["괜찮아요.", "별로 걱정은 안 돼요."])


def _a_diet(f: dict[str, Any], p: Patient, rng: random.Random) -> str:
    if f.get("appetite") == "poor":
        return rng.choice(["요즘 입맛이 없어서 잘 못 먹어요.", "조금밖에 못 먹어요."])
    return rng.choice(["네, 잘 먹어요.", "네, 잘 먹는 편이에요."])


def _a_dysphagia(f: dict[str, Any], p: Patient, rng: random.Random) -> str:
    return "가끔 사레가 들려요." if f.get("dysphagia") else "괜찮아요."


def _a_weight(f: dict[str, Any], p: Patient, rng: random.Random) -> str:
    ws, wc = f.get("weight_screen"), str(f.get("weight_change") or "")
    if ws == "loss":
        m = re.search(r"(\d+)kg", wc)
        return f"네, {m.group(1)}킬로 정도 빠졌어요." if m else "조금 빠졌어요."
    if ws == "gain":
        return "조금 쪘어요."
    return rng.choice(["비슷해요.", "변화 없어요."])


def _a_voiding(f: dict[str, Any], p: Patient, rng: random.Random) -> str:
    return {"frequency": "자주 마려워요.", "difficulty": "시원하게 안 나와요.", "incontinence": "가끔 새요.", "foley": "소변줄 하고 있어요.",
            "urgency": "급하게 마려워요."}.get(str(f.get("voiding")), rng.choice(["네, 괜찮아요.", "불편한 거 없어요."]))


def _a_bowel(f: dict[str, Any], p: Patient, rng: random.Random) -> str:
    return {"constipation": "변비가 좀 있어요.", "diarrhea": "요즘 설사를 해요.", "stoma": "장루로 봐요."}.get(str(f.get("bowel")), rng.choice(["네, 매일 봐요.", "네, 잘 봐요."]))


def _a_sleep(f: dict[str, Any], p: Patient, rng: random.Random) -> str:
    return {"poor": "요즘 잘 못 자요.", "hypnotic": "수면제 먹고 자요."}.get(str(f.get("sleep")), rng.choice(["네, 잘 자요.", "잘 자는 편이에요."]))


def _a_mobility(f: dict[str, Any], p: Patient, rng: random.Random) -> str:
    if f.get("mobility") == "device":
        return "보행기 밀고 다녀요." if f.get("adl") == "walker" else "지팡이 짚고 다녀요."
    return {"assist": "누가 잡아줘야 해요.", "bedrest": "휠체어 타요."}.get(str(f.get("mobility")), rng.choice(["네, 혼자 다녀요.", "네, 괜찮아요."]))


def _a_pain(f: dict[str, Any], p: Patient, rng: random.Random) -> str:
    nrs = int(f.get("nrs") or 0)
    if nrs == 0:
        return rng.choice(["지금은 안 아파요.", "아픈 데는 없어요."])
    site = str(f.get("pain_site") or "")
    lay = next((l for k, l in _LAY_SITE if k in site), site or "수술한 데")
    ch = _LAY_CHAR.get(str(f.get("pain_char") or ""), "")
    return f"{lay} {ch + ' ' if ch else ''}아파요. 한 {nrs}점 정도요."


def _a_sense(f: dict[str, Any], p: Patient, rng: random.Random) -> str | None:
    s = f.get("sense") or []
    if "hearing" in s:
        return "귀가 좀 어두워요."
    if "vision" in s:
        return "눈이 좀 침침해요."
    if "speech" in s or "foreign" in s:
        return None
    return rng.choice(["없어요.", "안경 쓰면 괜찮아요."])


def _a_fall(f: dict[str, Any], p: Patient, rng: random.Random) -> str:
    if f.get("fall_history") == "yes":
        cc = str(f.get("chief_complaint") or "")
        return "네, 이번에 넘어져서 왔어요." if any(w in cc for w in ("낙상", "미끄러", "넘어")) else "네, 한 번 넘어진 적 있어요."
    return rng.choice(["아니오, 없어요.", "없어요."])


def _a_caregiver(f: dict[str, Any], p: Patient, rng: random.Random) -> str:
    female = p.sex.startswith("여")
    return {"spouse": ("남편이" if female else "아내가") + " 있을 거예요.", "child": rng.choice(["딸이", "아들이"]) + " 와 있을 거예요.",
            "caregiver": "간병인 쓰려고요.", "none": "혼자 있을 거예요.", "intermittent": "낮에만 잠깐씩 올 거예요."}.get(str(f.get("caregiver")), "혼자 있을 거예요.")


def _a_smoking(f: dict[str, Any], p: Patient, rng: random.Random) -> str:
    return {"quit": "예전에 피우다 끊었어요.", "current": "하루 반 갑 정도 피워요."}.get(str(f.get("smoking")), "안 피워요.")


def _a_alcohol(f: dict[str, Any], p: Patient, rng: random.Random) -> str:
    return {"social": "가끔 마셔요.", "heavy": "거의 매일 마셔요."}.get(str(f.get("alcohol")), "안 마셔요.")


def _a_religion(f: dict[str, Any], p: Patient, rng: random.Random) -> str:
    v = str(f.get("religion") or "")
    return "없어요." if (not v or v == "무교") else f"{v}예요."


def _a_lmp(f: dict[str, Any], p: Patient, rng: random.Random) -> str:
    v = str(f.get("lmp") or "")
    return "폐경됐어요." if "폐경" in v else f"{v}이요."


def _a_weakness(f: dict[str, Any], p: Patient, rng: random.Random) -> str:
    if f.get("weakness") == "pos":
        note = str(f.get("weakness_note") or "다리")
        return f"{note.replace('환측 ', '아픈 쪽 ')}에 힘이 좀 없어요."
    return "없어요."


def _a_symptom(f: dict[str, Any], p: Patient, rng: random.Random) -> str:
    if f.get("symptom_screen") == "pos":
        return _LAY_SYMPTOM.get(str(f.get("symptom_note") or ""), "조금 있어요.")
    return rng.choice(["없어요.", "그런 건 없어요."])


# field -> (nurse questions, answer builder); answers come back None when the item is not asked of this patient
QA: dict[str, tuple[list[str], Callable[[dict[str, Any], Patient, random.Random], str | None]]] = {
    "history": (["혹시 고혈압이나 당뇨 같은 앓고 계신 병 있으실까요?", "평소에 치료받고 계신 병 있으세요?"], _a_history),
    "medications": (["지금 드시고 계신 약 있으세요?", "집에서 드시는 약은 뭐가 있어요?"], _a_meds),
    "antiplatelet": (["아스피린이나 피 묽게 하는 약은 끊고 오셨어요?"], _a_antiplatelet),
    "past_surgery": (["전에 수술 받으신 적 있으세요?", "수술하신 적 있으실까요?"], _a_past_surgery),
    "transfusion": (["수혈 받으신 적 있으세요?"], _a_transfusion),
    "allergy": (["약이나 음식에 알레르기 있으실까요?", "알레르기 있는 거 있으세요?"], _a_allergy),
    "supplements": (["건강식품이나 영양제 드시는 거 있으세요?"], _a_supplements),
    "family_history": (["가족 중에 암이나 큰 병 앓으신 분 계세요?"], _a_family),
    "family_none": (["가족 중에 암이나 큰 병 앓으신 분 계세요?"], _a_family),
    "emotion": (["입원하고 수술하시는 거 많이 걱정되세요?", "요즘 걱정되거나 불안한 거 있으세요?"], _a_emotion),
    "appetite": (["식사는 잘 하세요?", "요즘 입맛은 어떠세요?"], _a_diet),
    "dysphagia": (["삼키는 거 불편하신 건 없으세요?"], _a_dysphagia),
    "weight_change": (["최근에 몸무게 변화 있었어요?"], _a_weight),
    "voiding": (["소변 보시는 건 불편한 거 없으세요?"], _a_voiding),
    "bowel": (["대변은 잘 보세요?"], _a_bowel),
    "sleep": (["잠은 잘 주무세요?"], _a_sleep),
    "mobility": (["걷는 건 혼자 괜찮으세요?"], _a_mobility),
    "nrs": (["지금 아픈 데 있으세요? 0에서 10까지 하면 몇 점 정도예요?", "지금 통증 있으실까요? 10점 만점에 몇 점이에요?"], _a_pain),
    "sense": (["눈이나 귀 불편하신 건 없으세요?"], _a_sense),
    "fall_history": (["최근 6개월 동안 혹시 넘어진 적 있을까요?"], _a_fall),
    "caregiver": (["입원해 계시는 동안 보호자분은 누가 계세요?"], _a_caregiver),
    "smoking": (["담배는 피우세요?"], _a_smoking),
    "alcohol": (["술은 드세요?"], _a_alcohol),
    "religion": (["종교 있으세요?"], _a_religion),
    "lmp": (["마지막 생리는 언제였어요?"], _a_lmp),
    "weakness": (["팔다리에 힘 빠지는 데 있으세요?"], _a_weakness),
    "symptom_screen": (["그 외에 숨차거나 붓거나 하는 데 있으세요?"], _a_symptom),
}
# items whose answer already covers another field's question
_COVERS = {"family_none": "family_history", "weight_change": None}


def qa(field_key: str, form: dict[str, Any], patient: Patient, rng: random.Random, asked: set[str]) -> tuple[str, str] | None:
    """(question, answer) for this field, or None when it is narrated instead. ``asked`` dedupes paired fields."""
    if field_key not in QA:
        return None
    if field_key in ("family_none", "family_history"):
        if "family" in asked:
            return None
        asked.add("family")
    if field_key == "nrs" and "pain_site" in asked:
        return None
    if field_key == "weight_change" and form.get("weight_screen") in (None, "neg") and not form.get("weight_change"):
        return None
    questions, build = QA[field_key]
    answer = build(form, patient, rng)
    if not answer:
        return None
    asked.add(field_key)
    return rng.choice(questions), _answer(answer, patient)


def ack(rng: random.Random) -> str | None:
    return rng.choice(ACKS) if rng.random() < 0.25 else None


SPEAKER_PREFIX = {"nurse": "간호사: ", "patient": "환자: "}


def strip_prefix(line: str) -> tuple[str, str]:
    """'환자: 네, 잘 먹어요.' -> ('patient', '네, 잘 먹어요.'); unprefixed lines are the nurse's."""
    for sp, pre in SPEAKER_PREFIX.items():
        if line.startswith(pre):
            return sp, line[len(pre):].strip()
    return "nurse", line.strip()
