"""Virtual patient and random form generation for bulk recording."""
from __future__ import annotations

import random
import re
from datetime import datetime, timedelta
from typing import Any

from . import clinical
from .generator import Patient
from .phrase_store import formal_from_chart
from .templates import get_template
from .templates.base import Field

SURNAMES = ["김", "이", "박", "최", "정", "강", "조", "윤", "장", "임", "한", "오", "서", "신", "권", "황", "안", "송", "류", "홍",
            "전", "고", "문", "손", "양", "배", "백", "허", "유", "남", "심", "노", "하", "곽", "성", "차", "주", "우", "구", "민"]
GIVEN_M = ["민수", "영호", "철수", "성민", "준호", "동현", "재현", "정훈", "상우", "병철", "기훈", "태영", "현우", "진우", "영식",
           "종수", "만수", "경수", "대성", "성호", "우진", "지훈", "도현", "승현", "병호", "창수", "광수", "덕수", "길동", "석진"]
GIVEN_F = ["영희", "미경", "지영", "수진", "은정", "현주", "미숙", "정희", "순자", "혜진", "지은", "민정", "선영", "경희", "미영",
           "영숙", "옥순", "말순", "정순", "혜경", "수연", "유진", "소연", "다혜", "보람", "하늘", "은주", "숙자", "명희", "춘자"]

PROFESSORS = ["김민수", "이정호", "박상현", "최유진", "정우성", "강동원", "한지민", "윤석우", "장현식", "임채영", "오세훈", "서지혜"]

TEXT_POOLS: dict[str, list[str]] = {
    "chief_complaint": ["2개월 전부터 상복부 불편감, 체중 5kg 감소", "건강검진에서 우연히 발견된 종괴", "3주 전부터 간헐적 복통", "혈변 2회",
                        "우상복부 통증과 소화불량", "1개월 전부터 식후 더부룩함", "무릎 통증으로 보행 어려움", "낙상 후 우측 고관절 통증"],
    "onset": ["2개월 전부터", "3주 전부터", "1개월 전", "어제 저녁부터", "6개월 전부터 서서히"],
    "present_illness": ["8월 건강검진 위내시경에서 종괴 발견되어 조직검사상 선암 진단", "타병원 대장내시경에서 종괴 발견, 조직검사상 선암",
                        "외래 CT에서 담낭 결석 및 담낭염 소견", "응급실 CT에서 급성 충수염 진단", "유방 초음파 및 조직검사상 침윤성 유방암"],
    "history_detail": ["고혈압 10년, 당뇨 5년 경구약 복용", "고혈압 5년 약 복용 중", "당뇨 8년 인슐린 사용", "특이사항 없음", "협심증으로 스텐트 시술 3년 전"],
    "past_surgery": ["20년 전 충수절제술", "10년 전 제왕절개", "없음", "5년 전 담낭절제술", "2년 전 백내장 수술"],
    "allergy_reaction": ["두드러기", "가려움", "호흡곤란", "발진"],
    "medications": ["암로디핀 5mg, 메트포르민 500mg bid", "로사르탄 50mg qd", "메트포르민 500mg bid, 아토르바스타틴 20mg", "없음",
                    "아스피린 100mg, 클로피도그렐 75mg", "레보티록신 50mcg qd", "혈압약 트윈스타 40/5mg 하나씩 아침 식후",
                    "고지혈증약 로수바스타틴 10mg 저녁", "혈압약 하나 아침 식후, 당뇨약 메트포르민 아침저녁"],
    "intake_note": ["해산물 알레르기", "채식", "매운 음식 못 드심", "유제품 피함"],
    "weakness_note": ["오른쪽 다리", "왼쪽 팔", "환측 다리"],
    "symptom_note": ["식후 더부룩함", "다리 부종", "가끔 두근거림", "계단 오를 때 숨참"],
    "lmp": ["2026년 9월 30일", "2026년 10월 2일", "폐경"],
    "pain_desc": ["수술 부위 복부 쪽 쑤시는 느낌", "수술 부위 당기는 느낌", "움직일 때 수술 부위 찌르는 느낌", "수술 부위 묵직한 느낌"],
    "s6.fluid": ["하트만 덱스 주사액 1리터 컨트롤 세트로 40cc/hr", "하트만 1리터 60cc/hr", "N/S 1리터 KVO", "5DW 500cc 40cc/hr"],
    "s6.line": ["왼팔 22게이지", "오른손등 24게이지", "오른팔 20게이지", "왼손등 22게이지", "Lt arm 22G", "Rt hand 24G", "Lt forearm 20G"],
    "s6.wound": ["복부 단일공", "복부 4개 포트", "우측 발목 수술 부위", "하복부 정중절개"],
    "t1": ["오전 7시", "오전 7시 30분", "오전 6시 50분"], "t2": ["오전 8시", "오전 8시 10분"],
    "t3": ["오후 1시", "오후 12시 40분"], "t4": ["오후 1시 30분", "오후 2시", "오후 3시"],
    "s1.plan": ["수술 예정", "수술 후 조직검사 결과에 따라 추가 치료 결정 예정"],
    "supplements": ["오메가3", "홍삼", "비타민 D", "없음"],
    "family_history": ["부친 위암", "모친 당뇨", "없음", "형제 대장암", "부친 고혈압"],
    "weight_change": ["3kg 감소", "5kg 감소", "변화 없음", "2kg 증가"],
    "devices": ["없음", "PICC", "장루"],
    "religion": ["기독교", "불교", "천주교", "무교"],
    "op_date": ["내일 10월 14일 오전 8시", "내일 오전 8시 30분", "내일 오후 1시", "모레 오전 8시"],
    "npo_meds": ["혈압약은 아침 6시 소량의 물로", "항경련제는 소량의 물과 함께 복용", "허용 약 없음"],
    "prep_detail": ["오늘 저녁 8시 하제 복용 예정", "수술 당일 아침 관장 예정", "클리퍼 제모 시행함"],
    "duration": ["3~4시간", "2시간", "1시간 30분", "4~5시간"],
    "blood_type": ["A형 Rh+", "B형 Rh+", "O형 Rh+", "AB형 Rh+", "A형 Rh-"],
    "question": ["환자가 수술 후 식사 시작 시점을 질문하여 가스 배출 후 물부터 단계적으로 진행한다고 답변", "통증이 얼마나 심한지 질문하여 PCA로 조절 가능하다고 설명",
                 "입원 기간 질문하여 보통 7~10일 정도라고 설명", "특이 질문 없음"],
    "arrival_time": ["12시 30분", "오후 2시", "오전 11시 50분", "오후 4시 20분"],
    "vs_lead": ["도착 당시", "병실 도착 후", "오후 2시"],
    "iv": ["Lt arm 20G line", "Rt hand 22G line", "Lt forearm 22G IV line", "Rt arm 20G IV line", "Lt hand 24G line", "Rt forearm 20G line"],
    "p_iv_site": ["Lt arm", "Rt hand", "Lt forearm", "Rt arm", "왼팔", "오른손등"],
    "found_time": ["오전 10시", "오후 2시", "오후 6시", "새벽 3시", "오후 9시 30분"],
    "complaint": ["열감 조금 있다고 표현하고 오한은 없음", "오한 있다고 하심", "열감 없다고 하나 얼굴 붉어짐", "두통 호소"],
    "drain": ["JP 배액 serosanguineous 양상 40cc", "JP sanguineous 20cc", "JP serous 15cc", "배액관 없음",
              "우측 복부 JP 배액은 장액성으로 색 옅어지고 있음", "JP 장액혈성 30cc, 특이 변화 없음"],
    "judgement": ["수술 후 폐 확장 저하에 의한 발열 가능성", "수술 부위 감염 가능성", "요로 감염 가능성", "탈수 가능성"],
    "noti_time": ["오전 10시 10분", "오후 2시 15분", "오후 6시 5분", "새벽 3시 10분"],
    "noti_content": ["BT 38.1, BP 150/85, HR 92, 수술 부위 oozing 없고 JP 양상 변화 없으나 폐음 하부 감소되어 있고 심호흡 잘 안 되는",
                     "BT 38.4, HR 98, 오한 동반, 수술 부위 발적 없는", "BT 37.9, 소변 혼탁하고 배뇨 시 불편감 있는"],
    "orders": ["acetaminophen 1g IV 1회 투여, lung care 및 ambulation 격려, chest PA 촬영 후 결과 노티",
               "blood culture 2쌍, urine culture 시행 후 acetaminophen 1g IV", "CBC, CRP F/U 및 acetaminophen 650mg PO"],
    "med_given": ["오전 10시 20분 PRN acetaminophen 1g/100mL IV 30분간 점적", "오후 2시 30분 acetaminophen 650mg PO", "오후 6시 15분 PRN acetaminophen 1g IV"],
    "exam": ["chest PA 촬영 위해 목걸이와 환의 금속 단추 확인하고 제거 후 도보로 영상의학과", "blood culture 2쌍 채혈하고 urine culture 검체 보냈으며",
             "휠체어로 영상의학과 CT실"],
    "re_time": ["오전 11시 30분", "오후 4시", "오후 8시", "새벽 5시"],
    "s3_2.plan": ["chest PA 결과 판독 확인 후 주치의 노티 예정이며 4시간 간격으로 체온 추적 관찰", "배양 결과 확인 예정이며 2시간 후 체온 재측정",
                  "내일 아침 랩 F/U 예정"],
    "s5.plan": ["오전에 강화폐활량계 교육 재확인", "내일 수술 준비 및 금식 확인", "퇴원 교육 시행", "오전 외래 CT 이송 준비", "PICC 드레싱 교환"],
    "s3_1.plan": [], "s2.plan": [], "s4.plan": [],
    "discharge_date": ["오전", "오전 11시", "점심 전", "오후 3시 보호자 내원 후", "오후"],
    "course": ["수술 후 특이 합병증 없이 회복", "수술 후 발열 있었으나 호전", "수술 후 장폐색 없이 식이 진행 양호"],
    "discharge_meds": ["아세트아미노펜 650mg 하루 세 번 식후 5일분, 위장운동촉진제 하루 세 번 식전 2주분, 철분제 하루 한 번",
                       "아세트아미노펜 650mg 하루 세 번 3일분, 세파클러 하루 세 번 5일분", "진통제 5일분과 변비약 2주분"],
    "driving": ["운전은 2주 후, 복직은 외래 확인 후 가능함", "운전은 1주 후 가능함", "복직은 4주 후 가능함"],
    "opd": ["10월 27일 오전 10시 30분", "10월 30일 오후 2시", "11월 3일 오전 9시"],
    "opd_exam": ["외래 당일 8시 30분 채혈 후 진료 볼 것", "외래 전 CT 촬영할 것", "따로 영상검사나 혈액검사 없음"],
    "allergy": ["조영제", "페니실린", "NSAIDs", "없음", "새우"],
    "io": ["수액 2000, 소변 1800, JP 60", "수액 1800, 소변 1500, JP 40", "경구 1200 수액 1500, 소변 2100"],
    "fluid": ["하트만 80cc/hr", "N/S 60cc/hr", "5DW 40cc/hr", "하트만 100cc/hr"],
    "antibiotic": ["세파졸린 q8h", "세프트리악손 q24h", "항생제 없음", "메트로니다졸 q8h 추가"],
    "prn": ["트라마돌 1회", "항구토제 1회", "없음", "트라마돌 2회, 수면제 1회"],
    "transfusion": ["", "PRBC 1 pack 수혈 완료", "", ""],
    "line": ["Rt arm 22G line 하나, 10월 13일 삽입이라 내일 교환 예정", "Lt arm 20G line 하나, 오늘 교환함", "오른팔 말초 라인 하나, 오늘 교환함", "Lt hand 22G IV line 하나, 주입 잘 됨", "PICC 우측 상완, 주 1회 드레싱"],
    "other_tube": ["", "", "L-tube 자연 배액 중", ""],
    "lab": ["WBC 11.2, CRP 8.5로 어제보다 약간 상승", "Hb 9.8로 감소", "K 3.2로 감소하여 KCl 추가", "CRP 2.1로 정상 범위"],
    "glucose": ["식전 150~180으로 슬라이딩 스케일", "식전 120~140, 인슐린 없음", "식전 200 이상으로 RI 4단위 추가"],
    "imaging": ["chest PA 특이 소견 없음", "복부 CT 결과 확인 예정", ""],
    "pending": ["내일 아침 랩 결과 확인 후 미음 진행 여부 담당의 확인", "협진 회신 확인", "보호자 면담 요청 있어 주치의 확인 필요", "퇴원 처방 확인"],
}

VS_PROFILE = {
    "normal": {"sbp": (105, 140), "dbp": (60, 88), "hr": (62, 92), "rr": (16, 20), "bt": (36.2, 37.1), "spo2": (96, 99)},
    "fever": {"sbp": (120, 155), "dbp": (70, 92), "hr": (88, 110), "rr": (18, 24), "bt": (37.8, 38.9), "spo2": (94, 98)},
    "hypo": {"sbp": (82, 98), "dbp": (45, 60), "hr": (95, 120), "rr": (18, 24), "bt": (36.0, 36.8), "spo2": (93, 97)},
}


SURGICAL_TEMPLATES = {"s2", "s3_1", "s3_2"}  # chemo admissions never get pre/post-op records


def random_patient(rng: random.Random, template_key: str | None = None, scenario: str | None = None) -> Patient:
    """Draw a coherent patient from the ward knowledge base (clinical.py): diagnosis, surgery or
    chemo regimen, age/sex bias and (for chemo) cycle/day.  ``scenario`` forces one family."""
    if scenario and scenario in clinical.BY_KEY:
        sc = clinical.BY_KEY[scenario]
    else:
        pool = clinical.OPS if (template_key in SURGICAL_TEMPLATES) else clinical.SCENARIOS
        weights = [3 if s.kind == "op" else 1 for s in pool]   # ward is ~75% surgical
        sc = rng.choices(pool, weights=weights)[0]
    sex = sc.sex or rng.choice(["남", "여"])
    name = rng.choice(SURNAMES) + rng.choice(GIVEN_M if sex == "남" else GIVEN_F)
    age = rng.randint(*sc.age)
    base_day = rng.randint(1, 28)
    month = rng.randint(1, 12)
    common = dict(name=name, age=age, sex=sex, diagnosis=rng.choice(sc.dx), professor=rng.choice(PROFESSORS),
                  department=sc.dept, scenario=sc.key, op_date=f"{month}월 {base_day}일",
                  admission_date=f"{month}월 {max(1, base_day - 1)}일")
    if sc.kind == "chemo":
        return Patient(**common, surgery="", kind="chemo", regimen=sc.key, pod=None,
                       cycle=rng.randint(1, int(sc.form.get("_cycles") or 8)), day=rng.choice(sc.form.get("_days") or [1]))
    lo, hi = sc.los
    pod = {"s1": None, "s2": None, "s3_1": rng.choice([0, 1, 2]), "s3_2": rng.choice([1, 2, 3]),
           "s4": rng.randint(max(0, lo), max(lo, hi)), "s5": rng.randint(0, max(1, hi))}.get(template_key or "", rng.choice([1, 2, 3]))
    return Patient(**common, surgery=sc.key, pod=pod)


def _apply_scenario(form: dict[str, Any], template_key: str, fields: dict[str, Field], sc: clinical.Scenario,
                    rng: random.Random) -> None:
    """Narrow the random form to what is plausible for this surgery/regimen."""
    for raw_key, allowed in sc.form.items():
        if raw_key.startswith("_"):
            continue
        if "." in raw_key:
            tpl, key = raw_key.split(".", 1)
            if tpl != template_key:
                continue
        else:
            key = raw_key
            if f"{template_key}.{key}" in sc.form:
                continue  # template-specific override wins
        f = fields.get(key)
        if f is None:
            continue
        if allowed is None:
            form.pop(key, None)
            continue
        if f.kind == "multi":
            choice = rng.choice(allowed) if allowed and isinstance(allowed[0], list) else allowed
            valid = {o.value for o in f.options}
            form[key] = [v for v in choice if v in valid]
        elif f.kind == "select":
            choice = rng.choice(allowed) if isinstance(allowed, list) else allowed
            if any(o.value == choice for o in f.options):
                form[key] = choice
        elif isinstance(allowed, list):
            form[key] = rng.choice(allowed)
        else:
            form[key] = allowed


def random_datetime(rng: random.Random, around: datetime | None = None) -> datetime:
    around = around or datetime.now()
    day = around + timedelta(days=rng.randint(-20, 20))
    # typical charting moments
    hour, minute = rng.choice([(7, 30), (8, 10), (9, 0), (10, 30), (11, 10), (13, 10), (14, 0), (15, 30), (16, 10),
                               (18, 0), (19, 30), (20, 10), (21, 0), (22, 30), (23, 10), (1, 20), (3, 10), (5, 40)])
    minute = rng.choice([minute, rng.randint(0, 59)])
    return day.replace(hour=hour, minute=minute, second=0, microsecond=0)


def random_vitals(rng: random.Random, profile: str | None = None, with_spo2: bool = True) -> dict[str, Any]:
    profile = profile or rng.choices(["normal", "fever", "hypo"], weights=[75, 20, 5])[0]
    p = VS_PROFILE[profile]
    v = {
        "sbp": rng.randint(*p["sbp"]), "dbp": rng.randint(*p["dbp"]), "hr": rng.randint(*p["hr"]),
        "rr": rng.randint(*p["rr"]), "bt": round(rng.uniform(*p["bt"]), 1),
    }
    if with_spo2 and rng.random() < 0.7:
        v["spo2"] = rng.randint(*p["spo2"])
        v["o2"] = rng.choice(["room air", "", "O2 2L nasal", "O2 3L nasal"])
    else:
        v["spo2"] = ""
        v["o2"] = ""
    return v


def _random_number(f: Field, rng: random.Random) -> float | int:
    key = f.key
    ranges = {"nrs": (0, 7), "braden": (13, 23), "p_braden": (13, 23), "jhfrat": (2, 16), "p_jhfrat": (14, 22), "height": (148, 182), "weight": (42, 95),
              "bmi": (17.5, 31.0), "drain_amount": (5, 120), "bt_peak": (37.3, 38.9), "bt_now": (36.4, 37.6),
              "sbp": (80, 100), "dbp": (45, 62), "hr": (100, 125)}
    lo, hi = ranges.get(key, (f.min or 0, f.max or 10))
    if f.step and f.step < 1 or isinstance(lo, float):
        return round(rng.uniform(float(lo), float(hi)), 1)
    return rng.randint(int(lo), int(hi))


def jhfrat_score(form: dict[str, Any], patient: Patient | None) -> int:
    """Johns Hopkins Fall Risk Assessment Tool score from the facts already in the admission form
    (the ward's tool, user 2026-10-16): age, elimination, high-risk drugs, equipment, mobility, cognition."""
    age = (patient.age if patient else None) or 50
    s = 3 if age >= 80 else 2 if age >= 70 else 1 if age >= 60 else 0
    urin = form.get("voiding")
    s += 4 if urin == "both" else 2 if urin in ("frequency", "incontinence", "urgency") else 0
    drugs = sum([any(h in (form.get("history") or []) for h in ("htn", "heart")), form.get("sleep") == "hypnotic",
                 "dm" in (form.get("history") or []) and False])
    s += 5 if drugs >= 2 else 3 if drugs == 1 else 0
    devices = str(form.get("devices") or "")
    s += min(3, len([d for d in re.split(r"[,·/]", devices) if d.strip()])) if devices else 0
    mobility = form.get("mobility")
    s += {"device": 2, "assist": 4, "wheelchair": 2}.get(mobility or form.get("adl") or "", 0)
    s += {"drowsy": 1, "confuse": 3}.get(form.get("consciousness") or "", 0)
    if any(x in (form.get("sense") or []) for x in ("vision", "hearing")):
        s += 2
    return max(0, min(35, s))


def fall_level(score: int) -> str:
    return "low" if score <= 5 else "moderate" if score <= 13 else "high"


def braden_risk(score: int) -> str:
    return "최고위험" if score <= 9 else "고위험" if score <= 12 else "중등도 위험" if score <= 14 else "저위험" if score <= 18 else "위험 없음"


def _consistency(form: dict[str, Any], template_key: str, t, rng: random.Random, patient: Patient | None, sc) -> None:
    """Cross-field plausibility: the random fill is per field, so this removes the combinations a
    nurse would never chart (PCA with pain 0, stupor patient answering questions, catheter care when
    there is no catheter, PCA titration in a discharge record, fever of 41.6 ...)."""
    opts = {f.key: {o.value for o in f.options} for _, f in t.iter_fields() if f.kind == "select"}
    chemo = patient is not None and patient.kind == "chemo"
    if "purpose" in form and patient is not None:
        tox = chemo and chemo_toxicity(form.get("chief_complaint", ""))
        form["purpose"] = "symptom" if tox else ("chemo" if chemo else "op")   # THA patient must not be "admitted for tests"
    if "consciousness" in form and rng.random() < 0.85:
        form["consciousness"] = "alert"
    if template_key == "s1" and patient is not None:
        _derive_s1(form, patient, sc, rng)
    if template_key == "s5" and patient is not None and (patient.pod is not None or patient.kind == "chemo") \
            and str(form.get("plan", "")).startswith("내일 수술"):
        form["plan"] = "퇴원 교육 시행" if (patient.pod or 0) >= 3 else "오전에 강화폐활량계 교육 재확인"   # no "surgery tomorrow" after the op
    if template_key == "s4":
        if any(w in form.get("special_edu", "") for w in ("무거운", "운동")):
            form.pop("activity", None)   # the leaflet item already covers activity
        if "further" in form and patient is not None and not any(w in patient.diagnosis for w in ("암", "종양", "전이", "증식", "림프", "종괴")):
            form["further"] = "none"     # benign surgery: no "조직검사 결과 따라 보조 항암"
        if patient is not None and patient.department != "정형외과" and rng.random() < 0.7:
            form["referral"] = []        # most discharges have no referral (real recordings)
    if patient is not None and patient.department != "정형외과" and (patient.age or 0) < 70:
        for key in ("mobility", "adl"):   # a 30-year-old myoma patient does not arrive in a wheelchair
            if key in form and rng.random() < 0.9:
                form[key] = "independent"
    # fall risk: Johns Hopkins score from the form, level from the score (scenario may force high/low)
    forced = set(sc.form.get("fall") or []) if sc is not None and "fall" in sc.form else set()
    if template_key == "s1" and "jhfrat" in form and "fall" in form:
        if forced == {"high"} and form.get("mobility") == "independent":   # a forced high-risk patient walks with help
            form["mobility"], form["adl"] = "device", "walker"
        score = jhfrat_score(form, patient)
        if forced == {"high"}:
            score = max(score, 14 + rng.randint(0, 4))
        elif forced == {"low"}:
            score = min(score, 5)
        form["jhfrat"], form["fall"] = score, fall_level(score)
    elif "fall" in form and "moderate" in opts.get("fall", set()) and not forced and patient is not None:
        age = patient.age or 50
        form["fall"] = rng.choice(["high", "moderate"]) if age >= 80 else rng.choice(["moderate", "low", "low"]) if age >= 65 else "low"
    if "p_jhfrat" in form:
        form["p_jhfrat"] = max(int(form["p_jhfrat"]), 14)          # the high-risk protocol re-assesses as still high
    # pressure injury: Braden score ↔ risk band, and the admission skin finding
    if template_key == "s1" and "skin" in form:
        young_mobile = patient is not None and (patient.age or 0) < 65 and form.get("mobility") == "independent"
        if rng.random() < (0.95 if young_mobile else 0.8):
            form["skin"] = "intact"        # a pressure injury on admission is rare, and rarer in a walking 40-year-old
    if "p_braden" in form:
        form["p_braden_risk"] = braden_risk(int(form["p_braden"]))
    if template_key == "s1" and "braden" in form:
        if form.get("skin") == "pressure":
            form["braden"] = min(int(form["braden"]), 14)
        elif patient is not None and (patient.age or 0) < 65 and form.get("mobility") == "independent":
            form["braden"] = max(int(form["braden"]), 19)
        if "pressure_risk" in form:   # spoken as "욕창 n점으로 저위험군" — the band must match the score
            form["pressure_risk"] = {"최고위험": "very_high", "고위험": "high", "중등도 위험": "moderate", "저위험": "low", "위험 없음": "none"}[braden_risk(int(form["braden"]))]
    if template_key == "s1" and patient is not None:
        _derive_s1_problems(form, patient, rng)
    if form.get("consciousness") == "alert" and "orientation" in form and rng.random() < 0.9:
        form["orientation"] = "yes"   # an alert patient is almost always oriented
    if form.get("weight_screen") == "neg":
        form.pop("weight_change", None)  # "변화 없음" screen must not be followed by "5kg 감소"
    if form.get("consciousness") in ("stupor", "confuse"):
        if "responds" in form:
            form["responds"] = False
        if "orientation" in form and {"no", "partial"} <= opts.get("orientation", set()):
            form["orientation"] = "no" if form["consciousness"] == "stupor" else "partial"
    # pain score vs analgesia
    pm = form.get("pain_med") or form.get("pain_mgmt")
    for nrs_key in ("nrs", "nrs1"):
        if nrs_key in form:
            if pm in ("pca", "pca_prn") and form[nrs_key] < 1:
                form[nrs_key] = rng.randint(2, 5)
            if pm == "none" and form[nrs_key] > 2:
                form[nrs_key] = rng.randint(0, 2)
    if "pca_edu" in form and form.get("pain_med") != "pca":
        form["pca_edu"] = False
    # post-op day logic (S3-1)
    timing = form.get("timing")
    scenario_gd = bool(sc) and "gd" in (sc.form.get("diet_status") or [])
    if timing == "day0":
        if form.get("diet_status") in ("ld", "gd") and not scenario_gd:
            form["diet_status"] = rng.choice(["npo", "sow"])
        if form.get("ambulation_plan") == "walk_today":
            form["ambulation_plan"] = rng.choice(["evening_sit", "bedrest"])
    elif timing in ("pod1", "pod2"):
        if form.get("foley") == "keep":
            form["foley"] = rng.choice(["removed", "none"])
        if form.get("ambulation_plan") == "bedrest":
            form["ambulation_plan"] = "walk_today"
        if form.get("diet_status") == "npo":
            form["diet_status"] = rng.choice(["sow", "ld"])
    if form.get("weight_screen") in ("loss", "gain") and not form.get("weight_change"):
        form["weight_change"] = rng.choice(["3kg 감소", "5kg 감소", "4kg 정도 감소"] if form["weight_screen"] == "loss" else ["3kg 증가"])
    if form.get("weight_change") == "변화 없음":
        stable = next((v for v in ("none", "no", "stable") if v in opts.get("weight_screen", set())), None)
        if stable and form.get("weight_screen") in ("loss", "gain"):
            form["weight_screen"] = stable
        if form.get("weight_screen") in ("loss", "gain"):
            form["weight_change"] = rng.choice(["3kg 감소", "5kg 감소"])
        else:
            form.pop("weight_change", None)
    # glucose protocol: hypoglycaemia care goes with a low value, insulin with a high one
    if "p_bst_value" in form:
        if form.get("p_hypo_intervene"):
            form["p_bst_value"] = rng.randint(48, 68)
            form.pop("p_insulin_give", None)
        else:
            form["p_bst_value"] = min(int(form["p_bst_value"]), 380)
            if form["p_bst_value"] < 70:
                form["p_bst_value"] = rng.randint(90, 220)
        if "p_bst_re" in form:
            v = form["p_bst_value"]
            form["p_bst_re"] = rng.randint(100, 160) if v < 70 else rng.randint(max(110, v - 120), max(120, v - 20))
    # protocol items that contradict the record
    drops: list[str] = []
    fall = form.get("fall") if isinstance(form.get("fall"), str) else None
    if fall is not None:   # the fall protocol must match the assessed level (score 5 + "재사정 17점 고위험" is a contradiction)
        drops += ["p_env_"] if fall == "high" else ["p_fall_", "p_call_bell", "p_jhfrat"]
    no_drain = (template_key in ("s3_1", "s3_2", "s5", "s6") and form.get("drain") in (None, "none")) or \
               (template_key == "s4" and form.get("device") != "drain") or chemo
    if no_drain:
        drops.append("p_drain")
    no_foley = form.get("foley") in ("none", "removed") or form.get("voiding") in ("self", "foley_removed") or chemo or \
               (template_key == "s4" and form.get("device") != "foley")
    if no_foley:
        drops += ["p_foley", "p_self_void", "p_peri_care", "p_urine_check", "p_residual", "p_void_"]
    if form.get("diet_status") == "npo" or form.get("diet") == "npo":
        drops.append("p_meal")
    if template_key == "s4" or chemo or pm == "none" or (template_key == "s5" and pm not in (None, "pca", "pca_prn")):
        drops.append("p_pca_")
    if chemo:
        drops += ["p_wound", "p_dressing", "p_dsg"]
    for k in list(form):
        if any(k.startswith(d) for d in drops):
            form.pop(k)
    for pre in ("apain", "cpain"):
        if form.get(f"p_{pre}_score") is not None and int(form[f"p_{pre}_score"]) < 2 and \
                (form.get(f"p_{pre}_intervene") or form.get(f"p_{pre}_reassess")):
            form[f"p_{pre}_score"] = rng.randint(3, 7)  # nobody medicates a pain of 0
        s_, r_ = form.get(f"p_{pre}_score"), form.get(f"p_{pre}_re_score")
        if s_ is not None and r_ is not None and r_ >= s_:
            form[f"p_{pre}_re_score"] = max(0, int(s_) - rng.randint(1, 3))
    if form.get("meal1") == "npo":  # S6: still NPO at breakfast -> no lunch either
        if "meal2" in form:
            form["meal2"] = "npo"
    for k in ("p_temp", "p_recheck_temp"):
        if k in form and form[k] > 39.5:
            form[k] = round(rng.uniform(37.8, 39.2), 1)
    if "p_temp" in form and "p_recheck_temp" in form and form["p_recheck_temp"] >= form["p_temp"]:
        form["p_recheck_temp"] = round(form["p_temp"] - rng.uniform(0.3, 1.0), 1)


_SIDES = ("우측", "좌측", "양측")
_TRAUMA = ("골절", "낙상", "미끄러", "넘어", "사고", "외상", "삐끗")
# ponytail: curated mutually-exclusive keyword groups; add a tuple when a new scenario mixes aetiologies
_EXCLUSIVE = (
    ("골절", "무혈성 괴사", "골관절염", "류마티스", "회전근개"),
    ("발목", "손목|요골", "쇄골", "상완골|어깨", "다리|경골|하지"),
    ("내측", "외측"),
    ("갑상선암|유두암|결절", "그레이브스|항진증"),
    ("자궁내막종|자궁내막증", "기형종"),
    ("용종", "선암|암"),
    ("상피내암", "침윤성|선행 항암"),
    ("당뇨", "말초동맥", "외상"),
    ("후두암|후두 종괴|두경부암", "성대 마비", "삽관|인공호흡기"),
    ("사타구니|서혜부", "배꼽", "흉터|반흔"),
    ("내치핵", "외치핵|혈전성"),
    ("선행", "보조"),
    ("발진", "갑상선|호르몬", "저림|신경병증", "설사|탈수", "오심|구토", "발열|호중구", "혈압", "단백뇨"),
)
_TOXICITY = ("응급실", "심해져", "오심", "구토", "설사", "발열", "저림", "발진", "탈수", "혈압 상승", "단백뇨", "기능 저하", "감량", "보류")


def chemo_toxicity(text: str) -> bool:
    """A chemo admission for a side effect (설사로 탈수, 호중구감소성 발열) rather than the scheduled cycle."""
    return any(w in text for w in _TOXICITY)


def _member(group: tuple[str, ...], text: str) -> int | None:
    return next((i for i, m in enumerate(group) if re.search(m, text)), None)


def coherent_pool(dx: str, cands: tuple[str, ...]) -> list[str]:
    """Complaints/histories that do not contradict the diagnosis: same side (우측 유방암 ↔ 좌측 멍울),
    same trauma-ness (골관절염 ↔ 낙상 후 통증) and no other aetiology from the same exclusive group
    (대퇴골 경부 골절 ↔ 골관절염으로 치환술 예정).  Empty when nothing fits."""
    side = next((x for x in _SIDES if x in dx), None)
    trauma = any(w in dx for w in _TRAUMA)
    groups = [(g, m) for g in _EXCLUSIVE if (m := _member(g, dx)) is not None]

    def ok(c: str) -> bool:
        if side and any(x in c for x in _SIDES if x != side):
            return False
        if any(w in c for w in _TRAUMA) != trauma:
            return False
        return all(_member(g, c) in (None, m) for g, m in groups)
    return [c for c in cands if ok(c)]


def _coherent(rng: random.Random, dx: str, cands: tuple[str, ...]) -> str:
    return rng.choice(coherent_pool(dx, cands) or list(cands))


def _fill(text: str, patient: Patient | None, sc=None) -> str:
    """Chemo texts carry {cycle}/{cycles}/{day} so "TCH 4차 위해 입원" never disagrees with the patient's cycle."""
    if patient is None or patient.cycle is None:
        return text
    return (text.replace("{cycle}", str(patient.cycle)).replace("{day}", str(patient.day or 1))
            .replace("{cycles}", str((sc.form.get("_cycles") if sc else None) or patient.cycle)))


_HISTORY_W = {"htn": 5, "dm": 4, "dyslipidemia": 3, "heart": 2, "thyroid": 2, "stroke": 1, "lung": 1, "ckd": 1, "prediabetes": 1, "tb": 1, "liver": 1}
_YOUNG_HISTORY = ("thyroid", "dyslipidemia", "liver", "htn", "dm")
_DETAIL = {
    "htn": ["고혈압 {y}년 약 복용 중", "고혈압으로 {y}년째 외래 추적"], "dm": ["당뇨 {y}년 경구약 복용", "당뇨 {y}년 인슐린 사용"],
    "heart": ["협심증으로 스텐트 시술 {y}년 전", "심방세동으로 약 복용 중"], "stroke": ["{y}년 전 뇌경색, 후유증 없음"],
    "lung": ["COPD로 흡입기 사용 중"], "ckd": ["만성신질환 3기로 외래 추적 중"], "liver": ["B형 간염 보균"],
    "thyroid": ["갑상선 기능 저하로 신지로이드 복용 중"], "tb": ["{y}년 전 결핵 완치"], "prediabetes": ["당뇨 전단계로 식이 조절 중"],
    "dyslipidemia": ["고지혈증 약 복용 중"],
}
_MEDS = {
    "htn": ["암로디핀 5mg qd", "로사르탄 50mg qd", "텔미사르탄 40mg qd"], "dm": ["메트포르민 500mg bid", "글리메피리드 2mg qd"],
    "heart": ["비소프롤롤 5mg qd", "아스피린 100mg qd"], "stroke": ["클로피도그렐 75mg qd"], "lung": ["세레타이드 흡입기 bid"],
    "thyroid": ["신지로이드 50mcg qd"], "dyslipidemia": ["아토르바스타틴 20mg qd"], "liver": ["바라크루드 0.5mg qd"],
}
_SITE_BY_WORD = [("고관절", "우측 고관절"), ("무릎", "무릎"), ("슬관절", "무릎"), ("어깨", "어깨"), ("견관절", "어깨"), ("회전근개", "어깨"),
                 ("발목", "발목"), ("요골", "손목"), ("쇄골", "쇄골"), ("상완골", "어깨"), ("경골", "무릎 아래"), ("반월", "무릎"),
                 ("유방", "유방"), ("치핵", "항문"), ("직장", "항문"), ("탈장", "서혜부"), ("담낭", "우상복부"), ("결장", "복부"),
                 ("갑상선", "목"), ("전립선", "하복부"), ("방광", "하복부"), ("신장", "옆구리"), ("자궁", "하복부"), ("난소", "하복부"),
                 ("부비동", "코 주위"), ("발", "발")]


def _weighted_distinct(rng: random.Random, weights: dict[str, int], k: int) -> list[str]:
    pool = dict(weights)
    out: list[str] = []
    while pool and len(out) < k:
        keys = list(pool)
        pick = rng.choices(keys, weights=[pool[x] for x in keys])[0]
        out.append(pick)
        del pool[pick]
    return out


def _derive_s1(form: dict[str, Any], patient: Patient, sc, rng: random.Random) -> None:
    """One coherent patient instead of independent field draws: the chronic conditions decide the past-history
    detail, the medications and the antiplatelet answer; the complaint decides the route, vitals, diet, bowel,
    pain and nursing problems (user, 2026-10-16: "중구난방이면 안 만드는 게 낫다")."""
    age = patient.age or 50
    cc = f"{form.get('chief_complaint', '')} {form.get('present_illness', '')} {patient.diagnosis}"
    chemo = patient.kind == "chemo"
    tox = chemo and chemo_toxicity(form.get("chief_complaint", ""))
    forced_hist = sc is not None and ("s1.history" in sc.form or "history" in sc.form)
    if "history" in form and not forced_hist:
        p_none = 0.85 if age < 40 else 0.5 if age < 60 else 0.25
        if rng.random() < p_none:
            form["history"] = []
        else:
            w = {k: v for k, v in _HISTORY_W.items() if age >= 60 or k in _YOUNG_HISTORY}
            form["history"] = _weighted_distinct(rng, w, 1 if age < 60 else rng.choice([1, 1, 2, 2, 3]))
    hist = [h for h in (form.get("history") or []) if h in _HISTORY_W]
    if "history_detail" in form:
        if hist:
            form["history_detail"] = ", ".join(rng.choice(_DETAIL[h]).format(y=rng.randint(2, 15)) for h in hist[:2])
        else:
            form.pop("history_detail", None)
    if "medications" in form:
        meds = [rng.choice(_MEDS[h]) for h in hist if h in _MEDS]
        if "dm" in hist and "인슐린" in form.get("history_detail", ""):
            meds = [m for m in meds if "메트포르민" not in m and "글리메피리드" not in m] + ["인슐린 자가 주사 (란투스 14단위)"]
        if meds:
            form["medications"] = ", ".join(meds)
        else:
            form.pop("medications", None)
    if "antiplatelet" in form:
        on_apt = any(w in form.get("medications", "") for w in ("아스피린", "클로피도그렐"))
        form["antiplatelet"] = ("stopped" if not chemo else "taking") if on_apt else "na"
    if "route" in form:
        form["route"] = "er" if "응급실" in cc else "transfer" if "전원" in cc else "opd"
    if "vitals" in form:
        febrile = any(w in cc for w in ("발열", "오한", "호중구", "담낭염", "충수염", "농양", "감염"))
        v = random_vitals(rng, "fever" if febrile and rng.random() < 0.8 else "normal")
        if any(w in cc for w in ("탈수", "설사", "구토")):
            v["hr"] = rng.randint(96, 112)
        form["vitals"] = v
    nausea = tox and any(w in cc for w in ("오심", "구토", "식사 못"))
    if "diet" in form:
        if nausea:
            form["diet"] = rng.choice(["ld", "sd", "npo"])
        elif tox and "설사" in cc:
            form["diet"] = "sd"
        elif "dm" in hist and rng.random() < 0.6:
            form["diet"] = "dm"
        elif "htn" in hist and rng.random() < 0.2:
            form["diet"] = "lowsalt"
        else:
            form["diet"] = "gd"
    if "appetite" in form:
        form["appetite"] = "poor" if nausea or (tox and rng.random() < 0.5) else ("poor" if rng.random() < 0.15 else "good")
    if "dysphagia" in form:
        form["dysphagia"] = patient.department == "이비인후과" and rng.random() < 0.3
    if "bowel" in form:
        form["bowel"] = "diarrhea" if (tox and "설사" in cc) else rng.choices(["normal", "constipation"], weights=[88, 12] if age >= 60 else [95, 5])[0]
    if "voiding" in form and form.get("voiding") == "foley":
        form["voiding"] = "normal"
    if "voiding" in form and age < 60 and rng.random() < 0.92:
        form["voiding"] = "normal"
    if "sleep" in form and "sleep_screen" in form:
        form["sleep_screen"] = "neg" if form["sleep"] == "good" else ("pos" if rng.random() < 0.6 else "neg")
    if "nrs" in form:
        if chemo:
            nrs = rng.randint(2, 4) if (tox and any(w in cc for w in ("복통", "설사", "통증"))) else rng.choice([0, 0, 0, 1])
        elif any(w in cc for w in ("골절", "낙상", "미끄러", "탈구", "급성", "농양", "담낭염", "충수염", "치핵", "항문")):
            nrs = rng.randint(4, 7)
        elif any(w in cc for w in ("관절염", "통증", "저림", "탈출")):
            nrs = rng.randint(2, 5)
        else:
            nrs = rng.choice([0, 0, 0, 1, 2])
        form["nrs"] = nrs
        if nrs == 0:
            form.pop("pain_char", None)
            form.pop("pain_site", None)
        elif "pain_site" in form:
            site = next((s for w, s in _SITE_BY_WORD if w in cc), None)
            form["pain_site"] = site or ("복부" if chemo else form.get("pain_site", "수술 부위"))
    if "emotion" in form:
        form["emotion"] = ["anxiety"] if rng.random() < (0.3 if not chemo else 0.15) else ["none"]
    if "symptom_screen" in form:
        edema_ok = any(h in hist for h in ("heart", "ckd")) or patient.department == "정형외과"
        form["symptom_screen"] = "pos" if edema_ok and rng.random() < 0.4 else "neg"
        if form["symptom_screen"] == "neg":
            form.pop("symptom_note", None)
    if "weakness" in form:
        weak = "stroke" in hist or (patient.department == "정형외과" and rng.random() < 0.3)
        form["weakness"] = "pos" if weak and rng.random() < 0.7 else "neg"
        if form["weakness"] == "pos":
            form["weakness_note"] = "환측 다리" if patient.department == "정형외과" else rng.choice(["오른쪽 다리", "왼쪽 팔"])
        else:
            form.pop("weakness_note", None)
    if "social_work" in form and rng.random() < 0.95:
        form["social_work"] = "neg"
    # an elective admission is awake; confusion only in the very old after a fall
    if "consciousness" in form:
        form["consciousness"] = "confuse" if (age >= 75 and any(w in cc for w in ("낙상", "골절", "미끄러")) and rng.random() < 0.15) else "alert"
    if "isolation" in form:
        form["isolation"] = "contact" if rng.random() < 0.05 else "none"
    if "allergy" in form:
        form["allergy"] = ["none"] if rng.random() < 0.8 else [rng.choices(["food", "penicillin", "antibiotic", "nsaid", "contrast", "other"], weights=[4, 3, 2, 2, 1, 1])[0]]
    if "sense" in form:
        p_none = 0.65 if age >= 65 else 0.85
        form["sense"] = ["none"] if rng.random() < p_none else [rng.choices(["hearing", "vision", "speech", "foreign"], weights=[55, 40, 3, 2])[0]]
    if "adl" in form and "mobility" in form:   # the two mobility answers must agree
        form["adl"] = {"independent": "independent", "device": "walker", "assist": "assist", "bedrest": "wheelchair"}.get(form["mobility"], "independent")
    if isinstance(form.get("vitals"), dict):
        form["vitals"]["o2"] = "O2 2L nasal" if ("lung" in hist and rng.random() < 0.3) else "room air"
    if "pain_char" in form:
        dept = patient.department
        form["pain_char"] = rng.choice(["dull", "movement", "tender"] if dept == "정형외과" else ["dull"] if dept == "이비인후과" else ["dull", "colicky", "tender"])
    if "past_surgery" in form:
        female = patient.sex.startswith("여")
        cands = []
        if age >= 25:
            cands.append(f"{rng.randint(10, 30)}년 전 충수절제술")
        if age >= 60:
            cands.append(f"{rng.randint(1, 5)}년 전 백내장 수술")
        if female and 35 <= age <= 60:
            cands.append(f"{rng.randint(5, max(6, age - 28))}년 전 제왕절개")
        if age >= 40 and "담낭" not in cc:
            cands.append(f"{rng.randint(3, 10)}년 전 담낭절제술")
        cands.append("어릴 때 편도절제술")
        if chemo and "수술 후" in cc:
            treat = "유방" if "유방" in cc else "대장" if any(w in cc for w in ("대장", "결장", "직장")) else ""
            form["past_surgery"] = f"{rng.randint(1, 4)}개월 전 {treat + ' ' if treat else ''}수술"
        elif rng.random() < 0.45:
            form.pop("past_surgery", None)
        else:
            form["past_surgery"] = rng.choice(cands)
    if "intake_screen" in form:
        form["intake_screen"] = "decreased" if form.get("appetite") == "poor" else ("special" if rng.random() < 0.2 else "neg")
        if form["intake_screen"] != "special":
            form.pop("intake_note", None)
    if "depression_screen" in form:
        form["depression_screen"] = "pos" if rng.random() < 0.08 else "neg"
        if "selfharm" in form and form["depression_screen"] == "neg":
            form["selfharm"] = "none"
    if "weight_screen" in form:
        cancer = any(w in cc for w in ("암", "종양", "전이")) or chemo
        form["weight_screen"] = "loss" if (cancer and rng.random() < 0.3) else ("gain" if rng.random() < 0.08 else "neg")


def _derive_s1_problems(form: dict[str, Any], patient: Patient, rng: random.Random) -> None:
    """Nursing problems follow the facts (no 급성 통증 at NRS 0, no 수술 불안 for a chemo admission)."""
    if "nursing_problems" not in form:
        return
    chemo = patient.kind == "chemo"
    tox = chemo and chemo_toxicity(form.get("chief_complaint", ""))
    probs: list[str] = []
    if chemo:
        if tox and any(w in form.get("chief_complaint", "") for w in ("오심", "구토", "설사", "식사")):
            probs.append("nutrition")
        probs.append("infection")
        probs.append("knowledge")
    else:
        probs += ["anxiety", "knowledge"]
    if int(form.get("nrs") or 0) >= 3:
        probs.append("pain")
    if form.get("fall") in ("moderate", "high"):
        probs.append("fall")
    if form.get("pressure_risk") in ("moderate", "high", "very_high"):
        probs.append("skin")
    if form.get("appetite") == "poor" or form.get("weight_screen") == "loss":
        probs.append("nutrition")
    out: list[str] = []
    for p in probs:
        if p not in out:
            out.append(p)
    form["nursing_problems"] = out[:4] or ["knowledge"]


def audit(form: dict[str, Any], patient: Patient | None, template_key: str) -> list[str]:
    """Contradictions a nurse would catch; empty when the form is coherent. Used to re-draw random forms and
    shown as warnings in the app (user, 2026-10-16: 외래 입원인데 응급실 경유, 통증 0점인데 더 아프다 …)."""
    issues: list[str] = []
    cc = f"{form.get('chief_complaint', '')} {form.get('present_illness', '')}"
    hist = set(form.get("history") or [])
    detail = str(form.get("history_detail") or "")
    meds = str(form.get("medications") or "")
    if "응급실" in cc and form.get("route") not in (None, "er"):
        issues.append("응급실 경유로 왔는데 입원 경로가 응급실이 아님")
    if patient is not None and "purpose" in form:
        want = "symptom" if (patient.kind == "chemo" and chemo_toxicity(form.get("chief_complaint", ""))) else ("chemo" if patient.kind == "chemo" else "op")
        if form["purpose"] != want:
            issues.append("입원 목적이 환자 종류와 다름")
    if int(form.get("nrs") or 0) == 0 and ("pain_char" in form or "pain_site" in form):
        issues.append("통증 0점인데 통증 양상/부위가 있음")
    if form.get("sleep") == "good" and form.get("sleep_screen") == "pos":
        issues.append("잘 잔다는데 수면 선별 양성")
    if "당뇨" in detail and not hist & {"dm", "prediabetes"}:
        issues.append("과거력 상세에 당뇨가 있는데 기저질환에 없음")
    if "고혈압" in detail and "htn" not in hist:
        issues.append("과거력 상세에 고혈압이 있는데 기저질환에 없음")
    for words, need, label in ((("인슐린", "메트포르민", "글리메피리드"), {"dm"}, "당뇨약"), (("암로디핀", "로사르탄", "텔미사르탄"), {"htn"}, "혈압약"),
                               (("비소프롤롤", "콩코르"), {"heart"}, "심장약"), (("신지로이드", "레보티록신"), {"thyroid"}, "갑상선약"),
                               (("아토르바스타틴", "로수바스타틴"), {"dyslipidemia"}, "고지혈증약")):
        if any(w in meds for w in words) and not hist & need:
            issues.append(f"{label}을 먹는데 해당 기저질환이 없음")
    if "stroke" not in hist and "heart" not in hist and form.get("antiplatelet") in ("taking", "stopped") and not any(w in meds for w in ("아스피린", "클로피도그렐")):
        issues.append("항혈소판제 복용이라는데 약 목록에 없음")
    probs = set(form.get("nursing_problems") or [])
    if "pain" in probs and int(form.get("nrs") or 0) < 3:
        issues.append("통증이 없거나 약한데 간호 문제가 급성 통증")
    if "fall" in probs and form.get("fall") == "low":
        issues.append("낙상 저위험인데 간호 문제가 낙상 위험")
    if form.get("weight_screen") == "neg" and form.get("weight_change"):
        issues.append("체중 변화 없음인데 체중 변화 내용이 있음")
    vs = form.get("vitals") if isinstance(form.get("vitals"), dict) else None
    if vs and float(vs.get("bt") or 36.5) >= 38.0 and not any(w in cc + str(patient.diagnosis if patient else "") for w in ("발열", "오한", "호중구", "염", "감염", "농양")):
        issues.append("발열이 있는데 주호소·진단에 열 날 이유가 없음")
    if patient is not None and patient.kind == "chemo" and ("pain_char" in form) and int(form.get("nrs") or 0) == 0:
        issues.append("항암 환자 통증 0점인데 통증 양상 있음")
    if "adl" in form and "mobility" in form and (form["mobility"] == "independent") != (form["adl"] == "independent"):
        issues.append("보행 상태와 일상생활 보행 답이 다름")
    if form.get("appetite") == "good" and form.get("intake_screen") == "decreased":
        issues.append("식욕 양호인데 식사량 감소 선별")
    if form.get("allergy_reaction") and form.get("allergy") in (["none"], []):
        issues.append("알레르기 없음인데 반응 양상이 있음")
    if patient is not None and "제왕절개" in str(form.get("past_surgery") or "") and (not patient.sex.startswith("여") or (patient.age or 0) > 70):
        issues.append("제왕절개 과거력이 환자와 맞지 않음")
    return issues


def random_form(template_key: str, rng: random.Random, patient: Patient | None = None) -> dict[str, Any]:
    """Random form that passes ``audit`` (re-drawn up to 6 times; the derivations make this rare)."""
    form = _random_form_once(template_key, rng, patient)
    for _ in range(5):
        if not audit(form, patient, template_key):
            break
        form = _random_form_once(template_key, rng, patient)
    return form


def _random_form_once(template_key: str, rng: random.Random, patient: Patient | None = None) -> dict[str, Any]:
    t = get_template(template_key)
    sc = clinical.BY_KEY.get(patient.scenario) if patient is not None else None
    sc_pools = sc.pools if sc else {}
    form: dict[str, Any] = {}
    for _, f in t.iter_fields():
        if f.kind == "select":
            none_opt = next((o.value for o in f.options if o.value in ("none", "na", "no")), None)
            none_p = 0.9 if (patient is not None and (patient.age or 0) < 65) else 0.75
            if none_opt is not None and rng.random() < none_p:
                form[f.key] = none_opt   # DNR, isolation, delirium, pressure injury ... are the exception, not the rule
            elif f.default is not None and rng.random() < 0.3:
                form[f.key] = f.default
            else:
                form[f.key] = rng.choice(f.options).value
        elif f.kind == "multi":
            real = [o for o in f.options if o.value != "none"]
            if rng.random() < 0.2 and any(o.value == "none" for o in f.options):
                form[f.key] = ["none"]
            else:
                k = rng.choices([1, 2, 3], weights=[60, 30, 10])[0]
                k = min(k, len(real))
                form[f.key] = [o.value for o in rng.sample(real, k)] if k else []
        elif f.kind == "number":
            form[f.key] = _random_number(f, rng)
        elif f.kind == "bool":
            if f.key.startswith("p_"):
                continue  # protocol items are chosen per protocol below
            form[f.key] = rng.random() < 0.8 if f.default else rng.random() < 0.3
        elif f.kind == "text":
            pool = (sc_pools.get(f"{template_key}.{f.key}") or sc_pools.get(f.key)
                    or TEXT_POOLS.get(f"{template_key}.{f.key}", TEXT_POOLS.get(f.key)))
            if pool and template_key == "s4" and f.key == "special_edu":
                # discharge education: two or three items from the ward leaflet summary, one record
                k = min(len(pool), rng.choice([1, 2, 2, 3]))
                items = [formal_from_chart(_fill(x, patient, sc).rstrip(".") + ".") for x in rng.sample(list(pool), k)]
                form[f.key] = " ".join(items).rstrip(".")   # "교육함" -> "교육하였습니다" (discharge records are formal)
                continue
            if pool:
                val = _fill(rng.choice(pool), patient, sc)
                if val and val not in ("없음", "허용 약 없음", "특이 질문 없음", "검사 없음", "배액관 없음", "특이사항 없음", "항생제 없음", "특이 소견 없음", "변화 없음"):
                    form[f.key] = val
            elif f.default:
                form[f.key] = f.default
        elif f.kind == "vitals":
            if f.key == "re_vitals":
                form[f.key] = random_vitals(rng, "normal")
            elif template_key == "s3_2":
                form[f.key] = random_vitals(rng, "fever")
            else:
                form[f.key] = random_vitals(rng)
    # protocol checklist: pick 1-4 protocols for this recording, then 1-4 items each
    prot_secs = [sec for sec in t.sections if sec.group == "protocol"]
    if prot_secs:
        chosen = rng.sample(prot_secs, k=min(len(prot_secs), rng.choices([0, 1, 2, 3, 4], weights=[15, 30, 30, 15, 10])[0]))
        # fall high / low are mutually exclusive
        keys = {sec.key for sec in chosen}
        if "prot_fall_high" in keys and "prot_fall_low" in keys:
            chosen = [sec for sec in chosen if sec.key != rng.choice(["prot_fall_high", "prot_fall_low"])]
        for sec in chosen:
            bools = [f for f in sec.fields if f.kind == "bool"]
            for f in rng.sample(bools, k=min(len(bools), rng.randint(1, 4))):
                form[f.key] = True
    # keep things consistent with the scenario the patient was drawn from
    if sc is not None:
        first = sc.kind == "chemo" and patient.cycle == 1
        if sc.kind == "chemo" and not first and "present_illness" in form:
            pi_pool = coherent_pool(patient.diagnosis, sc.pi) or list(sc.pi)
            if all("1차 시작" in x for x in pi_pool):   # only first-cycle histories fit this diagnosis → make it cycle 1
                patient.cycle, first = 1, True
        if "chief_complaint" in form:
            pool = coherent_pool(patient.diagnosis, sc.cc) or list(sc.cc)
            pool = [x for x in pool if first or "1차 시작" not in x] or pool   # "보조 항암 1차 시작" only on cycle 1
            form["chief_complaint"] = _fill(rng.choice(pool), patient, sc)
        cc = form.get("chief_complaint", "")
        if "present_illness" in form:
            pool = coherent_pool(patient.diagnosis, sc.pi) or list(sc.pi)
            pool = coherent_pool(cc, tuple(pool)) or pool          # 발진 complaint ↔ 발진 history, not 갑상선
            if sc.kind == "chemo":
                pool = [x for x in pool if chemo_toxicity(x) == chemo_toxicity(cc)] or pool
                pool = [x for x in pool if first or "1차 시작" not in x] or pool
            form["present_illness"] = _fill(rng.choice(pool), patient, sc)
        if template_key == "s1" and sc.kind == "chemo":
            if chemo_toxicity(cc):   # side-effect admission: symptom onset is days, plan is treat-and-discharge
                form["onset"] = rng.choice(["어제부터", "2일 전부터", "3일 전부터", "일주일 전부터"])
                fluids = any(w in cc for w in ("설사", "구토", "탈수"))
                form["plan"] = rng.choice(["수액 치료 후 퇴원 예정", "증상 조절 후 퇴원 예정"] if fluids
                                          else ["증상 조절 후 퇴원 예정", "증상 호전 후 항암 일정은 외래에서 결정 예정"])
            else:
                form.pop("onset", None)
                form["plan"] = f"{sc.key} {patient.cycle}차 예정"
        if template_key == "s1" and sc.kind == "op":
            # plan names the actual surgery (not a generic "복강경 수술 예정" for a THA); drop it when the
            # present illness already ends in "... 예정"
            if "예정" in form.get("present_illness", ""):
                form.pop("plan", None)
            else:
                form["plan"] = f"{sc.abbr} 예정"
            # onset follows the complaint: trauma is days, incidental findings have no onset, the rest is months
            if any(w in cc for w in ("낙상", "미끄러", "넘어", "사고", "급성", "갑자기", "응급")):
                form["onset"] = rng.choice(["어제", "2일 전", "3일 전", "일주일 전"])
            elif any(w in cc for w in ("검진", "우연히", "발견")):
                form.pop("onset", None)
            elif "onset" in form:
                form["onset"] = rng.choice(["2개월 전부터", "3개월 전부터", "6개월 전부터 서서히", "1년 전부터", "1개월 전부터"])
        _apply_scenario(form, template_key, {f.key: f for _, f in t.iter_fields()}, sc, rng)
    _consistency(form, template_key, t, rng, patient, sc)
    if template_key == "s1" and patient is not None:
        female = patient.sex.startswith("여")
        if not female and rng.random() < 0.5:
            form.pop("marital", None)
        # the ward asks LMP only of gynecologic surgery patients (user, 2026-10-16); C-sec has no LMP talk
        if female and patient.kind == "op" and patient.department == "산부인과" and patient.surgery != "C-sec":
            m = re.match(r"(\d+)월", patient.admission_date or "")
            month = int(m.group(1)) if m else 10
            form["lmp"] = "폐경 상태" if (patient.age or 0) >= 52 else f"{month if rng.random() < 0.5 else (month - 2) % 12 + 1}월 {rng.randint(1, 28)}일"
        else:
            form.pop("lmp", None)
    if "family_history" in form and form.get("family_history") == "없음":
        form.pop("family_history", None)
        form["family_none"] = True
    elif "family_none" in form:
        form["family_none"] = False
    if "allergy" in form and form.get("allergy") == "없음":
        form.pop("allergy")
        form["allergy_none"] = True
    elif "allergy_none" in form and form.get("allergy"):
        form["allergy_none"] = False
    if template_key == "s1" and form.get("allergy") == ["none"]:
        form.pop("allergy_reaction", None)
    if template_key == "s5" and form.get("vs_summary") == "fever_resolved":
        if form.get("bt_now", 0) >= form.get("bt_peak", 0):
            form["bt_now"] = round(form["bt_peak"] - rng.uniform(0.4, 1.2), 1)
    if template_key == "s2":
        form["use_patient_surgery"] = True
        form.pop("procedure", None)
    return form
