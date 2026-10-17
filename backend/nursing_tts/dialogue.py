"""대화형 간호정보조사 (user 2026-10-17): the nurse asks (~까요? / ~세요?), the patient answers (~어요. / 네. / 아니오.),
and a patient of 80 or older answers in 반말 (~어. / 응. / 아니.). The interview opens with "어떻게 오셨어요?": the patient
tells the story in lay words (sometimes rambling, sometimes unsure of dates or what kind of surgery it was) and the
nurse extracts the chart facts in one confirmation line (``opening``).

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
             ("옆구리", "옆구리"), ("목", "목"), ("코 주위", "코 주위"), ("발", "발"), ("수술 예정 부위", "수술할 데"), ("수술 부위", "수술한 데")]
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
    if rng.random() < 0.25:                        # 이름은 모름 (user 2026-10-17: 기억 안 나는 것도)
        return f"네, {_join(meds)} 먹는데 이름은 잘 모르겠어요."
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
    r = rng.random()
    if r < 0.18:                                   # 기억이 흐릿: when
        return rng.choice([f"네, {lay} 했는데 한참 됐어요. 몇 년 전인지는 정확히 기억이 안 나요.", f"네, 꽤 오래전에 {lay} 했어요. 정확히 언제인지는 모르겠어요."])
    if r < 0.35 and any(k in raw for k in ("충수", "담낭", "제왕절개", "대장", "위")):   # 기억이 흐릿: what kind
        return rng.choice([f"네, {when} {lay} 했는데 복강경으로 했는지 그냥 열고 했는지는 잘 모르겠어요.",
                           f"네, {when} 배 수술을 하긴 했는데 맹장인지 뭔지 정확히는 기억이 안 나요." if "맹장" in lay else f"네, {when} {lay} 했는데 어떻게 했는지는 잘 기억이 안 나요."])
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


# --- opening: "어떻게 오셨어요?" → the patient tells the story in lay words (user 2026-10-17) --------------------
# Chart facts (주호소·발생 시기·경로·목적) are then *extracted* by the nurse in one confirmation line in chart language,
# so the transcript carries both the patient's wording and the exact chart terms; the form stays the label.
OPENERS = ["어떻게 오셨어요?", "어떻게 오시게 됐어요?", "어디가 불편해서 오셨어요?", "이번에 어떻게 오셨을까요?"]
COVERED_BY_OPENING = {"route", "purpose", "chief_complaint", "onset"}

# chief-complaint keyword → one lay sentence (the patient's words). Several rules may fire on one complaint; each
# becomes its own short sentence. Order matters: more specific first.
_LAY_CC: list[tuple[str, str]] = [
    (r"BRCA", "유전자 검사에서 유방암 위험이 높다고 해서 예방 수술 상담하러 왔어요."),
    (r"재건 (위해|예정)|동시 재건", "유방 수술하면서 재건도 같이 하기로 했어요."),
    (r"특이 증상 없이|우연히 발견", "아픈 데는 하나도 없었는데 검진에서 뭐가 보인다고 하더라고요."),
    (r"갑상선 전절제 후.*전이", "갑상선 수술하고 정기 검사 받았는데 목 쪽 림프절에 번졌다고 하더라고요."),
    (r"추적.*재발|재발 소견", "정기적으로 검사받고 있었는데 재발했다고 하더라고요."),
    (r"추적 중 (종괴|용종) 크기 증가|크기 증가", "정기 검사에서 혹이 커졌다고 하더라고요."),
    (r"검진.*(발견|소견|용종|석회화|병변|비후)", "건강검진에서 뭐가 보인다고 해서 검사를 더 했어요."),
    (r"추적 중.*(커짐|림프절)", "정기 검사 받다가 목 옆에 림프절이 커졌다고 하더라고요."),
    (r"반복 제왕절개|제왕절개 위해|예정 제왕절개", "이번에도 제왕절개 하기로 해서 날짜 맞춰 왔어요."),
    (r"전치태반", "태반이 아래쪽에 있다고 해서 제왕절개 하기로 했어요."),
    (r"CA-125|수치 상승", "피검사에서 수치가 높게 나왔다고 하더라고요."),
    (r"회장루 복원|장루 복원", "장루 다시 막는 수술 하러 왔어요."),
    (r"확장기|보형물 교체", "확장기 넣어 둔 거 보형물로 바꾸러 왔어요."),
    (r"인공호흡기|기관절개", "기계 호흡을 오래 해서 목에 구멍을 내기로 했다고 하더라고요."),
    (r"후두암|기도 폐쇄", "목에 암이 있어서 숨길이 막힐 수 있다고 하더라고요."),
    (r"(\S+암) 진단|진단받고", "암이라고 해서 수술하러 왔어요."),
    (r"장이 빠져나옴|항문으로 장", "변 볼 때 항문으로 뭐가 빠져나와요."),
    (r"흉터 부위|수술 흉터", "전에 수술한 자리가 불룩하게 튀어나왔어요."),
    (r"잔변감|가는 변", "변을 봐도 시원하지 않고 가늘게 나왔어요."),
    (r"폐경 후 질 출혈|질 출혈", "생리도 끝났는데 피가 비쳤어요."),
    (r"생리통", "생리통이 점점 심해졌어요."),
    (r"근종", "자궁에 혹이 있다고 하더라고요."),
    (r"괴사", "발가락이 까맣게 죽어 간다고 하더라고요."),
    (r"조직검사 후 유방암 진단|조직검사상 유방암", "조직검사 했더니 유방암이라고 하더라고요."),
    (r"갑상선 기능항진", "갑상선 약을 먹어도 조절이 안 된다고 수술하자고 하더라고요."),
    (r"장루 주위 피부", "장루 주변 피부가 자꾸 짓물러서요."),
    (r"진통 있어 내원|분만 진행", "진통이 와서 왔는데 진행이 안 된다고 하더라고요."),
    (r"항암 (후|중).*(설사|발열|호중구|구토|오심|발진|혈압|단백뇨)", "항암 맞고 나서 몸이 안 좋아져서 왔어요."),
    (r"항암.*(위해 입원|차)|선행 항암|보조 항암|표적치료|유지", "항암 맞으러 왔어요."),
    (r"손으로 밀어 넣|항문 탈출|탈출", "항문이 밖으로 빠져나와서 손으로 밀어 넣어야 들어가요."),
    (r"혈변|항문.*출혈|선홍색 출혈|배변 (시|후).*출혈|항문 출혈", "변 볼 때 피가 났어요."),
    (r"변실금", "변이 새기도 하고요."),
    (r"점액", "점액 같은 게 나오기도 했어요."),
    (r"고관절 통증", "엉덩이 쪽이 계속 아팠어요."),
    (r"절뚝", "절뚝거리면서 다녔어요."),
    (r"무릎 (안쪽 |바깥쪽 )?(통증|손상|삐끗)|무릎.*아프", "무릎이 아팠어요."),
    (r"잠김|펴지지 않", "무릎이 걸려서 잘 안 펴지더라고요."),
    (r"어깨 통증|어깨.*아프", "어깨가 많이 아팠어요."),
    (r"팔.*(못 올|올리기 어려|안 올라)", "팔이 잘 안 올라가요."),
    (r"잠 못 잠|잠을 못", "밤에 아파서 잠을 못 잤어요."),
    (r"발목 통증|발목", "발목이 아프고 부었어요."),
    (r"쇄골", "쇄골 쪽이 많이 아팠어요."),
    (r"손목", "손목이 아프고 부었어요."),
    (r"다리 통증|하지 통증|다리.*아프", "다리가 너무 아팠어요."),
    (r"보행 불가|걷기 힘|보행 어려|걷지 못", "걷지를 못하겠더라고요."),
    (r"식후 우상복부|우상복부", "밥 먹고 나면 오른쪽 윗배가 아팠어요."),
    (r"상복부 (불편|통증)", "명치 쪽이 더부룩하고 불편했어요."),
    (r"하복부 (종괴|압박)|하복부.*만져", "아랫배에 뭐가 만져지고 묵직했어요."),
    (r"우하복부", "오른쪽 아랫배가 아팠어요."),
    (r"하복부 (통증|불편)|하복부", "아랫배가 아팠어요."),
    (r"복부 팽만", "배가 빵빵하게 불렀어요."),
    (r"간헐적 복통|복통 간헐|복통|복부 통증", "배가 가끔씩 아팠어요."),
    (r"소화불량|더부룩", "소화도 잘 안 됐어요."),
    (r"체중.*감소", "살도 좀 빠졌어요."),
    (r"생리 과다", "생리 양이 너무 많았어요."),
    (r"빈혈", "빈혈이 있다고 하더라고요."),
    (r"빈뇨", "소변이 자주 마려웠어요."),
    (r"배뇨 곤란", "소변이 시원하게 안 나왔어요."),
    (r"PSA", "검사에서 전립선 수치가 높다고 하더라고요."),
    (r"혈뇨", "소변에 피가 섞여 나왔어요."),
    (r"호흡곤란|숨", "숨이 많이 찼어요."),
    (r"코막힘", "코가 계속 막혔어요."),
    (r"콧물", "누런 콧물이 계속 났어요."),
    (r"후각 저하", "냄새를 잘 못 맡게 됐어요."),
    (r"두통", "머리도 아팠어요."),
    (r"목 앞쪽 멍울|목.*멍울", "목 앞에 뭐가 만져졌어요."),
    (r"유두 분비물", "젖꼭지에서 뭐가 나왔어요."),
    (r"유방 (종괴|멍울)|유방.*(촉지|만져)|종괴 촉지|멍울", "가슴에 멍울이 만져졌어요."),
    (r"옆구리", "옆구리가 좀 불편했어요."),
    (r"발 궤양", "발에 난 상처가 안 낫고 심해졌어요."),
    (r"발열|열", "열도 났어요."),
    (r"설사", "설사를 계속 했어요."),
    (r"오심|구토", "속이 울렁거리고 토했어요."),
    (r"발진", "얼굴에 뭐가 많이 났어요."),
    (r"혈압 상승", "혈압이 많이 올랐어요."),
    (r"탈장|사타구니|서혜부", "사타구니가 불룩하게 튀어나왔어요."),
    (r"배꼽 주위|튀어나옴", "배꼽 주위가 불룩하게 튀어나왔어요."),
    (r"종괴|결절|병변|용종|석회화|이상 소견", "검사에서 뭐가 보인다고 하더라고요."),
]
_LAY_CC_LAST = [(r"통증|아픔", "거기가 계속 아팠어요.")]   # only when nothing more specific matched
_LAY_CAUSE: list[tuple[str, str]] = [   # trauma cause → prefix for the first symptom sentence
    (r"교통사고", "교통사고가 나서"), (r"자전거 사고", "자전거 타다가 넘어져서"), (r"축구 중", "축구하다가 다쳐서"),
    (r"계단에서", "계단에서 넘어져서"), (r"낙상|넘어진|넘어져", "넘어져서"), (r"무거운 것 든", "무거운 걸 들고 나서"), (r"삐끗", "삐끗하고 나서"),
]
_NATIVE = {1: "한", 2: "두", 3: "세", 4: "네", 5: "다섯", 6: "여섯", 7: "일곱", 8: "여덟", 9: "아홉", 10: "열", 12: "열두"}
_ROUTE_LAY = {
    "opd": ["그래서 외래 보고 입원하라고 해서 왔어요.", "동네 병원에서 큰 병원 가 보라고 해서 외래 봤거든요. 그래서 입원했어요.", "교수님 외래에서 입원하자고 하셔서요."],
    "er": ["너무 심해서 응급실로 왔어요.", "밤에 응급실 왔다가 입원하게 됐어요."],
    "transfer": ["다른 병원에서 여기로 옮겨 왔어요.", "거기서는 안 된다고 해서 이쪽으로 옮겼어요."],
}
_ROUTE_CHART = {"opd": "외래", "er": "응급실", "transfer": "타병원에서 전원"}
_PURPOSE_CHART = {"op": "수술 위해", "chemo": "항암 치료 위해", "exam": "검사 위해", "symptom": "증상 조절 위해"}
_DIGRESSIONS = ["처음엔 별거 아니겠지 하고 그냥 뒀거든요.", "원래 병원을 잘 안 가는 편인데요.", "전에는 이런 적이 한 번도 없었거든요.", "요새 들어 더 심해지더라고요."]


def _onset_lay(onset: str, rng: random.Random) -> tuple[str, str]:
    """'2개월 전부터' -> ('두 달 전부터', '') or, when the patient is vague, ('', '한 두 달쯤 됐을 거예요, 정확히는 기억이 안 나요.')."""
    m = re.match(r"(\d+)(개월|주|년|일)\s*전(부터)?(\s*서서히)?", onset)
    if not m:
        return (onset.replace("서서히", "조금씩") + ("" if onset.endswith("부터") else "부터"), "") if onset else ("", "")
    n, unit = int(m.group(1)), m.group(2)
    num = _NATIVE.get(n, str(n))
    lay = {"개월": f"{num} 달", "주": f"{n}주", "년": "작년" if n == 1 else f"{n}년", "일": {2: "이틀", 3: "사흘"}.get(n, f"{n}일")}[unit]
    lay = (lay if lay == "작년" else lay + " 전") + "부터" + (" 조금씩" if m.group(4) else "")
    if unit in ("개월", "년") and rng.random() < 0.3:
        approx = f"{num} 달" if unit == "개월" else ("일 년" if n == 1 else f"{n}년")
        return "", rng.choice([f"{'' if num == '한' else '한 '}{approx}쯤 됐을 거예요. 정확히는 기억이 안 나요.", f"{approx}쯤 된 것 같은데 정확히는 모르겠어요."])
    return lay, ""


def lay_complaint(cc: str, rng: random.Random) -> list[str]:
    """Sentences the patient says for a chart complaint; [] when no rule knows the wording."""
    cause = next((lay for pat, lay in _LAY_CAUSE if re.search(pat, cc)), "")
    hits: list[tuple[int, str]] = []
    covered = ""
    for pat, lay in _LAY_CC:
        m = re.search(pat, cc)
        if m and lay not in covered:
            hits.append((m.start(), lay))
            covered += lay
        if len(hits) >= 3:
            break
    if not hits:
        hits = [(m.start(), lay) for pat, lay in _LAY_CC_LAST if (m := re.search(pat, cc))]
    hits.sort()
    out = [lay for _, lay in hits]
    if cause and out:
        out[0] = f"{cause} {out[0]}"
    return out


def opening(form: dict[str, Any], patient: Patient, rng: random.Random) -> list[tuple[str, str]]:
    """[(nurse 'how did you come in?'), (patient story), (nurse chart-language confirmation)]."""
    cc = str(form.get("chief_complaint") or "")
    onset_lay, onset_vague = _onset_lay(str(form.get("onset") or ""), rng)
    sents = lay_complaint(cc, rng)
    chemo = patient.kind == "chemo"
    if not sents:
        sents = ["몸이 좀 안 좋아서 검사를 했는데 수술해야 한다고 하더라고요." if not chemo else "항암 맞으러 왔어요."]
    # no "두 달 전부터" in front of a story that starts with a finding or a decision instead of a symptom
    screening = bool(re.search(r"검진|추적|우연히", cc))
    detected = screening or bool(re.search(r"재발|BRCA|재건|유지|위해 입원", cc)) or any(w in sents[0] for w in ("하더라고요", "하기로", "하러 왔어요", "검사를 더", "상담"))
    if onset_lay and not detected and not chemo:
        cause = any(re.search(pat, cc) for pat, _ in _LAY_CAUSE)
        sents[0] = f"{onset_lay.replace('부터', '에') if cause else onset_lay} {sents[0]}"   # 일주일 전에 넘어져서 / 두 달 전부터 아팠어요
    for i in range(1, len(sents)):
        sents[i] = rng.choice(["", "", "그리고 ", "그러면서 "]) + sents[i]
    if onset_vague and not detected and not chemo:
        sents.insert(1, onset_vague)
    if rng.random() < 0.45 and not chemo and (screening or not detected):   # 장황: a digression or two that add no chart fact
        pool = ["아픈 데는 하나도 없었어요.", "그냥 검진 받은 건데 깜짝 놀랐어요."] if screening else list(_DIGRESSIONS)
        if not screening:
            female = patient.sex.startswith("여")
            who = "애들이" if (patient.age or 50) >= 60 else ("남편이" if female else "집사람이")
            pool.append(f"{who} 하도 가 보라고 해서요.")
            if (patient.age or 50) < 65:
                pool.append("일이 바빠서 계속 미루다가요.")
        k = 2 if rng.random() < 0.3 else 1
        for d in rng.sample(pool, min(k, len(pool))):
            sents.insert(min(len(sents), 1 + rng.randrange(0, len(sents))), d)
    route = str(form.get("route") or "opd")
    if not chemo and route in _ROUTE_LAY:
        sents.append(rng.choice(_ROUTE_LAY[route]))
    elif chemo and route == "er":
        sents.append("응급실 왔다가 입원하게 됐어요.")
    elif chemo:                                               # a regular cycle: which one, and that it is on schedule
        cyc = getattr(patient, "cycle", None)
        if cyc:
            sents.append(f"이번이 {_NATIVE.get(int(cyc), str(cyc))} 번째예요.")
        sents.append(rng.choice(["날짜 맞춰서 왔어요.", "외래에서 하라는 대로 입원했어요.", "지난번처럼 2박 3일 하고 가는 거예요."]) if rng.random() < 0.9 else "")
        sents = [x for x in sents if x]
    lead = rng.choice(["", "", "그게, ", "아, 그게 ", "음, "])
    story = lead + " ".join(sents)
    # the nurse extracts the chart facts from the story
    onset = str(form.get("onset") or "")
    rl, pl = _ROUTE_CHART.get(route, "외래"), _PURPOSE_CHART.get(str(form.get("purpose") or "op"), "")
    if not cc:                                                # hand-made form without a complaint: confirm only the route/purpose
        confirm = f"네, {rl} 통해 {pl} 입원하셨고요."
    elif "입원" in cc:
        confirm = rng.choice([f"네, 그러면 {cc}(이)시네요.", f"{cc}(이)시고요."])
    else:
        confirm = rng.choice([f"네, 그러면 {onset} {cc}(으)로 {rl} 통해 {pl} 입원하신 거네요.", f"네, 주호소는 {onset} {cc}(이)고, {rl} 통해 {pl} 입원하셨고요.",
                              f"네, {cc}(으)로 오셨고, {rl} 통해 {pl} 입원하셨네요."])
    confirm = re.sub(r"\s{2,}", " ", confirm).replace(" ,", ",").strip()
    return [("nurse", rng.choice(OPENERS)), ("patient", _answer(story, patient)), ("nurse", fix_josa(confirm))]


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


def _followup(field_key: str, answer: str, form: dict[str, Any]) -> str:
    """The nurse pins down what a vague answer left open (and puts the chart fact into the transcript)."""
    vague = "기억이 안 나" in answer or "모르겠" in answer
    if not vague:
        return ""
    if field_key == "past_surgery":
        raw = str(form.get("past_surgery") or "")
        lay = next((l for k, l in _LAY_SURGERY if k in raw), raw)
        return f"네, {lay} 하셨고요." if "맹장인지 뭔지" not in answer else "네, 맹장 수술이요. 알겠습니다."
    if field_key == "medications":
        return "네, 약 봉투나 처방전 있으시면 이따 보여 주세요."
    return ""


def qa(field_key: str, form: dict[str, Any], patient: Patient, rng: random.Random, asked: set[str]) -> tuple[str, str, str] | None:
    """(question, answer, nurse follow-up or "") for this field, or None when it is narrated instead. ``asked`` dedupes paired fields."""
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
    return rng.choice(questions), _answer(answer, patient), fix_josa(_followup(field_key, answer, form))


def ack(rng: random.Random) -> str | None:
    return rng.choice(ACKS) if rng.random() < 0.25 else None


SPEAKER_PREFIX = {"nurse": "간호사: ", "patient": "환자: "}


def strip_prefix(line: str) -> tuple[str, str]:
    """'환자: 네, 잘 먹어요.' -> ('patient', '네, 잘 먹어요.'); unprefixed lines are the nurse's."""
    for sp, pre in SPEAKER_PREFIX.items():
        if line.startswith(pre):
            return sp, line[len(pre):].strip()
    return "nurse", line.strip()
