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
    "intake_note": ["해산물 알레르기", "채식 식단", "매운 음식 섭취 어려움", "유제품 불내증"],
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
    "npo_meds": ["혈압약은 아침 6시 소량의 물로", "갑상선약은 아침 소량의 물로"],
    "prep_detail": ["오늘 저녁 8시 하제 복용 예정", "수술 당일 아침 관장 예정", "클리퍼 제모 시행함"],
    "duration": ["3~4시간", "2시간", "1시간 30분", "4~5시간"],
    "blood_type": ["A형 Rh+"] * 34 + ["O형 Rh+"] * 28 + ["B형 Rh+"] * 27 + ["AB형 Rh+"] * 11,   # Korea; Rh- is ~0.2% (was 18%)
    "question": ["수술 후 식사 시작 시점 질문하여 가스 배출 후 물부터 단계적으로 진행한다고 설명함", "통증이 얼마나 심한지 질문하여 PCA로 조절 가능하다고 설명함",
                 "입원 기간 질문하여 수술 후 경과 보고 결정된다고 설명함", "수술 후 언제부터 걸을 수 있는지 질문하여 다음 날부터 보행 시작한다고 설명함"],
    "arrival_time": ["12시 30분", "오후 2시", "오전 11시 50분", "오후 4시 20분"],
    "vs_lead": ["도착 당시", "올라오신 직후", "오후 2시"],
    "iv": ["Lt arm 20G line", "Rt hand 22G line", "Lt forearm 22G line", "Rt arm 20G line", "Lt hand 24G line", "Rt forearm 20G line"],   # "IV는 … IV line"
    "p_iv_site": ["Lt arm", "Rt hand", "Lt forearm", "Rt arm", "왼팔", "오른손등"],
    "found_time": ["오전 10시", "오후 2시", "오후 6시", "새벽 3시", "오후 9시 30분"],
    "complaint": ["열감 조금 있다고 표현하고 오한은 없음", "오한 있다고 하심", "열감 없다고 하나 얼굴 붉어짐", "두통 호소"],
    "drain": ["JP 배액 serosanguineous 양상 40cc", "JP bloody하게 20cc", "JP serous 15cc", "배액관 없음",
              "우측 복부 JP 배액은 장액성으로 색 옅어지고 있음", "JP serosanguineous하게 30cc, 특이 변화 없음"],
    "judgement": ["수술 후 폐 확장 저하에 의한 발열 가능성", "수술 부위 감염 가능성", "요로 감염 가능성", "탈수 가능성"],
    "noti_time": ["오전 10시 10분", "오후 2시 15분", "오후 6시 5분", "새벽 3시 10분"],
    "noti_content": ["BT 38.1, BP 150/85, HR 92, 수술 부위 oozing 없고 JP 양상 변화 없으나 폐음 하부 감소되어 있고 심호흡 잘 안 되는",
                     "BT 38.4, HR 98, 오한 동반, 수술 부위 발적 없는", "BT 37.9, 소변 turbid하고 배뇨 시 불편감 있는"],
    "orders": ["acetaminophen 1g IV 1회 투여, lung care 및 ambulation 격려, chest PA 촬영 후 결과 노티",
               "blood culture 2쌍, urine culture 시행 후 acetaminophen 1g IV", "CBC, CRP F/U 및 acetaminophen 650mg PO"],
    "med_given": ["오전 10시 20분 PRN acetaminophen 1g/100mL IV 30분간 점적", "오후 2시 30분 acetaminophen 650mg PO", "오후 6시 15분 PRN acetaminophen 1g IV"],
    "exam": ["chest PA 촬영 위해 목걸이와 환의 금속 단추 확인하고 제거 후 도보로 영상의학과", "blood culture 2쌍 채혈하고 urine culture 검체 보냈으며",
             "휠체어로 영상의학과 CT실"],
    "re_time": ["오전 11시 30분", "오후 4시", "오후 8시", "새벽 5시"],
    "s3_2.plan": ["chest PA 결과 판독 확인 후 주치의 노티 예정이며 4시간 간격으로 체온 추적 관찰", "배양 결과 확인 예정이며 2시간 후 체온 재측정",
                  "내일 아침 랩 F/U 예정"],
    "s5.plan": ["오전에 강화폐활량계 교육 재확인", "내일 수술 준비 및 금식 확인", "퇴원 교육 시행", "PICC 드레싱 교환"],   # 2026-10-18: "오전 외래 CT 이송 준비" fit nobody
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
    "line": ["Rt arm 22G line 하나, 오늘 교환함", "Lt arm 20G line 하나, 오늘 교환함", "오른팔 말초 라인 하나, 오늘 교환함", "Lt hand 22G IV line 하나, 주입 잘 됨"],
    "other_tube": ["", "", "L-tube 자연 배액 중", ""],
    "lab": ["WBC 11.2, CRP 8.5로 어제보다 약간 상승", "Hb 9.8로 감소", "K 3.2로 감소하여 KCl 추가"],   # _derive_s5 redraws the numbers by POD
    "glucose": ["식전 150~180으로 슬라이딩 스케일 적용 중", "식전 120~140으로 인슐린 없이 조절 중", "식전 200 넘어서 RI 4단위 추가 투여"],
    "imaging": ["chest PA 특이 소견 없음", "복부 CT 결과 확인 예정", ""],
    "pending": ["내일 아침 랩 결과 보고 미음 진행 여부", "협진 회신", "보호자 면담 요청 건", "퇴원 처방"],   # frames add "확인 …"
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
    dx_pool = [d for d in sc.dx if "삽관" not in d] if template_key == "s1" else list(sc.dx)   # an intubated ICU patient is not interviewed
    common = dict(name=name, age=age, sex=sex, diagnosis=rng.choice(dx_pool or list(sc.dx)), professor=rng.choice(PROFESSORS),
                  department=sc.dept, scenario=sc.key, op_date=f"{month}월 {base_day}일",
                  admission_date=f"{month}월 {max(1, base_day - 1)}일")
    if sc.kind == "chemo":
        return Patient(**common, surgery="", kind="chemo", regimen=sc.key, pod=None,
                       cycle=rng.randint(1, int(sc.form.get("_cycles") or 8)), day=rng.choice(sc.form.get("_days") or [1]))
    lo, hi = sc.los
    pod = {"s1": None, "s2": None, "s3_1": 0, "s3_2": rng.randint(1, max(1, min(3, hi))),   # no POD 3 event after a day surgery
           "s4": rng.randint(max(0, lo), max(lo, hi)), "s5": rng.randint(0, max(1, hi)),
           "s6": rng.randint(1, max(1, min(3, hi)))}.get(template_key or "", rng.choice([1, 2, 3]))   # 2026-10-18: Breast mass excision POD 3
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


def _parse_clock(text: str) -> int | None:
    """'오후 2시 30분' / '새벽 3시' / '12시 30분' -> minutes since midnight (ward clock as written by _clock); None without a time."""
    m = re.search(r"(새벽|오전|오후|아침|저녁|밤)?\s*(\d{1,2})\s*시(?:\s*(\d{1,2})\s*분|\s*(반))?", text or "")
    if not m:
        return None
    h = int(m.group(2))
    mi = int(m.group(3)) if m.group(3) else (30 if m.group(4) else 0)
    if m.group(1) in ("오후", "저녁", "밤") and h < 12:
        h += 12
    elif m.group(1) in ("새벽", "오전", "아침") and h == 12:
        h = 0
    return (h % 24) * 60 + mi


def _month_day(text: str) -> tuple[int, int] | None:
    m = re.match(r"\s*(\d{1,2})월\s*(\d{1,2})일", text or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def record_datetime(template_key: str, patient: Patient, form: dict[str, Any], rng: random.Random,
                    now: datetime | None = None) -> datetime:
    """When the record is dictated: on the patient's own timeline and after the record's own clock (user 2026-10-17, 맥락 —
    a "POD 0" note dated months away from its operation, recorded before the patient reached the ward, or a progress note
    timed 10:30 that charts the 23:00 round).  S1 on the admission day (외래 10~16시, 응급실 18~23시), S2 the afternoon or
    evening before the operation ("내일 수술"), S3-1 on the operation day 15~45 min after the ward arrival, S3-2 after the
    event's re-assessment, S4 on the discharge morning, S5 at a shift change (07·15·23시), S6 after the 23:00 round.
    The year puts the record within the past twelve months."""
    now = now or datetime.now()
    md = _month_day(patient.op_date) or (now.month, now.day)
    adm_md = _month_day(patient.admission_date)
    chemo = patient.kind == "chemo"
    shift_days = max(0, (patient.day or 1) - 1) if chemo else (patient.pod or 0)

    def days(year: int) -> tuple[datetime, datetime, datetime]:
        op = datetime(year, md[0], md[1])
        adm = datetime(year, *adm_md) if adm_md else op - timedelta(days=1)
        return op, adm, op + timedelta(days=shift_days)

    def record_day(year: int) -> datetime:
        op, adm, day_n = days(year)
        return {"s1": adm, "s2": op - timedelta(days=1), "s3_1": op}.get(template_key, day_n)

    year = now.year if record_day(now.year).date() <= now.date() else now.year - 1
    op, adm, day_n = days(year)
    t = template_key
    if t == "s1":
        day, mins = adm, (rng.randint(18 * 60, 23 * 60 + 30) if form.get("route") == "er" else rng.randint(10 * 60, 16 * 60 + 30))
    elif t == "s2":
        day, mins = op - timedelta(days=1), rng.randint(14 * 60, 20 * 60 + 30)
    elif t == "s3_1":
        arrival = _parse_clock(str(form.get("arrival_time") or ""))
        day, mins = op, (arrival if arrival is not None else rng.randint(12 * 60, 16 * 60)) + rng.randint(15, 45)
    elif t == "s3_2":
        found, again = _parse_clock(str(form.get("found_time") or "")), _parse_clock(str(form.get("re_time") or ""))
        if again is None:
            again = rng.randint(9 * 60, 21 * 60)
        if found is not None and again < found:
            again += 24 * 60                                     # the re-assessment ran past midnight
        day, mins = day_n, again + rng.randint(10, 40)
    elif t == "s4":
        day, mins = day_n, rng.randint(8 * 60 + 30, 10 * 60 + 40)  # discharge morning, before the 오전 11시 discharge
    elif t == "s5":
        shift = int(form.get("_shift") or 0) or (23 if form.get("gas_out") else rng.choice([7, 15, 23]))   # _derive_s5 picks it
        if shift != 7:
            form.pop("sleep", None)       # "밤에 잘 주무셨습니다" belongs to the 07:00 handover
        day, mins = day_n, shift * 60 + rng.randint(0, 40)
    elif t == "s6":
        last = _parse_clock(str(form.get("t8") or "")) or 23 * 60
        day, mins = day_n, min(23 * 60 + 59, last + rng.randint(5, 25))
    else:
        day, mins = day_n, rng.randint(9 * 60, 17 * 60)
    return day + timedelta(minutes=mins)


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
              "sbp": (80, 100), "dbp": (45, 62), "hr": (100, 125), "nrs1": (1, 6), "nrs4": (0, 3), "bt3": (36.3, 37.4),
              # checklist details: what a ward actually charts (RI 65단위, 잔뇨 771cc were the old 0~max draws)
              "p_insulin_unit": (2, 10), "p_urine_amount": (200, 600), "p_void_amount": (150, 400), "p_residual": (0, 80), "p_spo2": (94, 99),
              "p_rr": (16, 24), "p_o2_flow": (1, 5), "p_spiro_count": (8, 12), "p_spiro_ball": (2, 3), "p_drain_amount": (10, 150),
              "p_temp": (37.8, 39.0), "p_recheck_temp": (36.8, 37.8), "p_apain_score": (3, 7), "p_cpain_score": (3, 6), "p_apain_re_score": (0, 3), "p_cpain_re_score": (1, 3)}
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
    s += {"device": 2, "assist": 4, "wheelchair": 2, "bedrest": 2}.get(mobility or form.get("adl") or "", 0)   # 휠체어·침상 = transfer needs help
    s += {"drowsy": 1, "confuse": 3}.get(form.get("consciousness") or "", 0)
    if any(x in (form.get("sense") or []) for x in ("vision", "hearing")):
        s += 2
    if form.get("fall_history") == "yes":
        s += 5                                   # JHFRAT: one fall in the 6 months before admission
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
    if patient is not None and template_key in ("s2", "s3_1", "s3_2", "s4", "s5"):
        {"s2": _derive_s2, "s3_1": _derive_s3_1, "s3_2": _derive_s3_2, "s4": _derive_s4, "s5": _derive_s5}[template_key](form, patient, sc, rng)
    if patient is not None and template_key == "s6":
        _derive_s6(form, patient, sc, rng, t)
    if template_key == "s5" and patient is not None and (patient.pod is not None or patient.kind == "chemo") \
            and str(form.get("plan", "")).startswith("내일 수술"):
        form["plan"] = "퇴원 교육 시행" if (patient.pod or 0) >= 3 else "오전에 강화폐활량계 교육 재확인"   # no "surgery tomorrow" after the op
    if template_key == "s4":
        if "further" in form and patient is not None and not any(w in patient.diagnosis for w in ("암", "종양", "전이", "증식", "림프", "종괴")):
            form["further"] = "none"     # benign surgery: no "조직검사 결과 따라 보조 항암"
        if patient is not None and patient.department != "정형외과" and rng.random() < 0.7:
            form["referral"] = []        # most discharges have no referral (real recordings)
    if patient is not None and patient.department != "정형외과" and (patient.age or 0) < 70:
        for key in ("mobility", "adl"):   # a 30-year-old myoma patient does not arrive in a wheelchair (2026-10-18: 23세 ESS "부축 필요")
            if key in form:
                form[key] = "independent"
    # fall risk: Johns Hopkins score from the form, level from the score (scenario may force high/low)
    forced = set(sc.form.get("fall") or []) if sc is not None and "fall" in sc.form else set()
    if template_key == "s1" and "jhfrat" in form and "fall" in form:
        score = jhfrat_score(form, patient)   # 2026-10-18 2차 검수: "낙상 17점" from facts worth 4 (forced high-risk faked the number)
        if forced == {"low"} and score > 5:      # make the facts low-risk instead of faking the number (score must match the form)
            for k, v in (("sense", ["none"]), ("voiding", "normal"), ("mobility", "independent"), ("adl", "independent"),
                         ("fall_history", "no"), ("consciousness", "alert")):
                if k in form:
                    form[k] = v
            if form.get("sleep") == "hypnotic":
                form["sleep"] = "good"
            if form.get("devices"):
                form["devices"] = ""
            score = jhfrat_score(form, patient)
        form["jhfrat"], form["fall"] = score, fall_level(score)
    elif "fall" in form and "moderate" in opts.get("fall", set()) and not forced and patient is not None:
        age = patient.age or 50
        form["fall"] = rng.choice(["high", "moderate"]) if age >= 80 else rng.choice(["moderate", "low", "low"]) if age >= 65 else "low"
    if "p_jhfrat" in form:
        form["p_jhfrat"] = max(int(form["p_jhfrat"]), 14)          # the high-risk protocol re-assesses as still high
    # pressure injury: Braden score ↔ risk band, and the admission skin finding
    if template_key == "s1" and "skin" in form:
        young_mobile = patient is not None and (patient.age or 0) < 65 and form.get("mobility") == "independent"
        sore = patient is not None and re.search(r"궤양|(?<!무혈성 )괴사|압궤|짓무름", f"{patient.diagnosis} {form.get('chief_complaint', '')}")
        if sore and not chemo:
            form["skin"] = "wound"         # 당뇨발 궤양·괴사·압궤·장루 주위 짓무름 (2026-10-18: "피부 상태 양호함")
        elif form.get("skin") == "pressure" and form.get("mobility") in ("independent", "device"):
            form["skin"] = "intact"        # a sacral pressure ulcer belongs to someone who cannot get up
        elif chemo or rng.random() < (0.95 if young_mobile else 0.8):   # a chemo cycle admission has no "피부 상처" to explain
            form["skin"] = "intact"        # a pressure injury on admission is rare, and rarer in a walking 40-year-old
    if "p_braden" in form:
        form["p_braden_risk"] = braden_risk(int(form["p_braden"]))
    if template_key == "s1" and "braden" in form:
        # 2026-10-18 2차 검수: 84세 독립 보행에 "욕창 14점 중등도" — the score follows activity and mobility
        lo, hi = {"independent": (19, 23), "device": (17, 21), "assist": (13, 17), "bedrest": (12, 16)}.get(str(form.get("mobility")), (16, 22))
        if form.get("appetite") == "poor" or form.get("bowel") == "incontinence":
            lo, hi = max(9, lo - 2), hi - 1
        form["braden"] = rng.randint(lo, hi)
        if form.get("skin") == "pressure":
            form["braden"] = min(int(form["braden"]), 14)
        if "pressure_risk" in form:   # spoken as "욕창 n점으로 저위험군" — the band must match the score
            form["pressure_risk"] = {"최고위험": "very_high", "고위험": "high", "중등도 위험": "moderate", "저위험": "low", "위험 없음": "none"}[braden_risk(int(form["braden"]))]
    if template_key == "s1" and patient is not None:
        _derive_s1_problems(form, patient, rng)
    if form.get("consciousness") == "alert" and "orientation" in form and (template_key == "s1" or rng.random() < 0.9):
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
        if form.get("ambulation_plan") == "walk_today" and not (sc is not None and (sc.form.get("ambulation_plan") or []) == ["walk_today"]):
            form["ambulation_plan"] = rng.choice(["evening_sit", "bedrest"])   # arthroscopy that walks the same day keeps it
    elif timing in ("pod1", "pod2"):
        if form.get("foley") == "keep" and not (sc is not None and set(sc.form.get("foley") or []) == {"keep"}):   # RALRP keeps it for weeks
            form["foley"] = rng.choice(["removed", "none"])
        if form.get("ambulation_plan") == "bedrest" and not (sc is not None and sc.key == "BKA"):
            form["ambulation_plan"] = "walk_today"
        if form.get("diet_status") == "npo":
            form["diet_status"] = rng.choice(["sow", "ld"])
    if template_key == "s3_1" and "abdomen" in form:   # the diet sentence already tells the gas story
        d = form.get("diet_status")
        if d == "npo":
            form["abdomen"] = rng.choices(["soft", "distended"], weights=[9, 1])[0]
        elif d in ("sow", "ld") and rng.random() < 0.5:
            form["abdomen"] = "soft"
        else:
            form.pop("abdomen")
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
    no_drain = (template_key in ("s3_1", "s3_2", "s5") and form.get("drain") in (None, "none")) or \
               (template_key == "s4" and form.get("device") != "drain") or chemo or (template_key == "s6" and not _scenario_drains(sc))
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
    # S3-1: 금식(물도 금지)인데 경구 PRN을 드셨다고 하지 않음 — the diet may have become NPO in the post-op day logic above
    if template_key == "s3_1" and form.get("diet_status") == "npo" and form.get("pain_med") == "prn_po":
        form["pain_med"] = "prn_iv"
    # the rules above may change score inputs (의식·보행·배뇨…) after the score was set: keep score, level and problems in sync
    if template_key == "s1" and "jhfrat" in form and "fall" in form and forced not in ({"high"}, {"low"}):
        score = jhfrat_score(form, patient)
        if score != int(form["jhfrat"]):
            form["jhfrat"], form["fall"] = score, fall_level(score)
            if patient is not None:
                _derive_s1_problems(form, patient, rng)


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
    ("후두암|후두 종괴|두경부암|상기도 폐쇄", "성대 마비", "삽관|인공호흡기"),
    ("사타구니|서혜부|음낭", "배꼽", "흉터|반흔"),
    ("내치핵", "외치핵|혈전성"),
    ("선행", "보조"),
    # 2026-10-18 검수: 진단·주호소·현병력이 다른 이야기 (제왕절개 거대아/진통/둔위, 재건 즉시/지연/확장기, 위암/대장암, 고식/보조)
    ("전치태반", "둔위", "반복|이전 제왕", "진통|분만 진행", "거대아", "쌍둥이"),
    ("즉시|동시|NSM", "지연|DIEP|전절제 후|결손", "확장기|보형물 교체"),
    ("위암", "대장|결장|직장"),
    ("고식적|전이성", "보조|선행|수술 시행|수술 후"),
    ("만성", "급성|오한|응급실"),
    # 2026-10-18 2차 검수(간호정보조사 7,000개): 진단·주호소·현병력·과거 수술이 서로 다른 병
    ("난소|CA-125", "내막암|증식증|내막 조직검사|질 출혈|질출혈|내막 비후"),
    ("근종", "선근증", "증식증|내막 비후", "내막암"),
    ("섬유선종", "엽상", "유두종|유두 분비물"),
    ("용종", "결석|담석|담낭염"),
    ("양성", "신세포암"),
    ("상행결장", "맹장"),
    ("3도", "4도"),
    ("재발|전절제 후", "전절제 및"),
    ("응급실", "중환자실|삽관|인공호흡기"),
    # 2026-10-18 2차 검수: 손목 골절 퇴원에 "목발 보행 교육 완료·체중 부하 금지", 어깨 수술에 "보행기"
    ("손목|요골|쇄골|상완골|어깨|견관절|회전근개|팔걸이|외전 보조기|수술한 팔|손가락", "발목|다리|경골|하지|무릎|슬관절|고관절|대퇴|반월|목발|체중 부하|보행기|발가락"),
    ("발진", "갑상선|호르몬", "저림|신경병증", "설사|탈수", "오심|구토", "발열|호중구", "혈압", "단백뇨"),
)
_TOXICITY = ("응급실", "심해져", "오심", "구토", "설사", "발열", "저림", "발진", "탈수", "혈압 상승", "단백뇨", "기능 저하", "감량", "보류")


def chemo_toxicity(text: str) -> bool:
    """A chemo admission for a side effect (설사로 탈수, 호중구감소성 발열) rather than the scheduled cycle."""
    return any(w in text for w in _TOXICITY)


def _member(group: tuple[str, ...], text: str) -> int | None:
    return next((i for i, m in enumerate(group) if re.search(m, text)), None)


_SEX_ONLY = {"남": re.compile(r"음낭|고환|전립선"), "여": re.compile(r"자궁|난소|생리|월경|질 출혈|질 분비")}


def coherent_pool(dx: str, cands: tuple[str, ...], trauma: bool = True, sex: str | None = None) -> list[str]:
    """Complaints/histories that do not contradict the diagnosis: same side (우측 유방암 ↔ 좌측 멍울),
    same trauma-ness (골관절염 ↔ 낙상 후 통증) and no other aetiology from the same exclusive group
    (대퇴골 경부 골절 ↔ 골관절염으로 치환술 예정).  Empty when nothing fits."""
    side = next((x for x in _SIDES if x in dx), None)
    is_trauma = any(w in dx for w in _TRAUMA)
    groups = [(g, m) for g in _EXCLUSIVE if (m := _member(g, dx)) is not None]
    other_sex = _SEX_ONLY["남" if sex.startswith("여") else "여"] if sex else None   # 2026-10-18: 54세 여자 "음낭 부종 경미"

    def ok(c: str) -> bool:
        if other_sex is not None and other_sex.search(c):
            return False
        if side and any(x in c for x in _SIDES if x != side):
            return False
        if trauma and any(w in c for w in _TRAUMA) != is_trauma:
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
            form["history"] = ["none"]       # said ("과거력 없습니다") and asked in the dialogue, not left out (2026-10-18)
        else:
            w = {k: v for k, v in _HISTORY_W.items() if age >= 60 or k in _YOUNG_HISTORY}
            form["history"] = _weighted_distinct(rng, w, 1 if age < 60 else rng.choice([1, 1, 2, 2, 3]))
    hist = [h for h in (form.get("history") or []) if h in _HISTORY_W]
    if "history_detail" in form:
        if hist:
            form["history_detail"] = ", ".join(rng.choice(_DETAIL[h]).format(y=rng.randint(2, 15)) for h in hist[:2])
        else:
            form.pop("history_detail", None)
    if True:   # the med list follows the history even when the random fill left the field out (2026-10-18: 고혈압인데 약 없음)
        meds = [rng.choice(_MEDS[h]) for h in hist if h in _MEDS]
        if "심방세동" in form.get("history_detail", ""):   # AF (2026-10-17: "심방세동으로 약 복용 중" + "항응고제 복용 안 하십니다")
            meds = [m for m in meds if "아스피린" not in m and "비소프롤롤" not in m] + ["비소프롤롤 5mg qd", "아픽사반 5mg bid"]
        if "dm" in hist and "인슐린" in form.get("history_detail", ""):
            meds = [m for m in meds if "메트포르민" not in m and "글리메피리드" not in m] + ["인슐린 란투스 14단위 자가 주사"]
        if meds:
            form["medications"] = ", ".join(meds)
        else:
            form["medications"] = "복용 중인 약 없음"   # → "복용 중인 약 없습니다"; the dialogue asks and hears "없어요"
    if "심방세동" in form.get("history_detail", "") and "아픽사반" not in str(form.get("medications") or ""):
        # the med list may not have been drawn at all — an AF patient is still on rate control and a NOAC
        kept = [m for m in str(form.get("medications") or "").split(", ") if m and "아스피린" not in m and "비소프롤롤" not in m]
        form["medications"] = ", ".join(kept + ["비소프롤롤 5mg qd", "아픽사반 5mg bid"])
    if "antiplatelet" in form:
        held = next((w for w in ("아픽사반", "리바록사반", "에독사반", "와파린", "클로피도그렐", "아스피린") if w in form.get("medications", "")), "")
        form["antiplatelet"] = ("stopped" if not chemo else "taking") if held else "na"
        if held:   # NOACs stop 2 days before, antiplatelets a week
            form["apt_drug"], form["apt_hold"] = held, ("이틀 전" if held in ("아픽사반", "리바록사반", "에독사반") else "1주 전")
    if "route" in form:
        form["route"] = "er" if re.search(r"응급실|진통|분만 진행", cc) else "transfer" if "전원" in cc else "opd"   # labour comes through the ER
    if "vitals" in form:
        febrile = any(w in cc for w in ("발열", "오한", "호중구", "농양", "감염")) or \
            (bool(re.search(r"담낭염|충수염", cc)) and bool(re.search(r"급성|오한|응급", cc)))   # chronic cholecystitis is afebrile
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
        elif "dm" in hist:
            form["diet"] = "dm"           # 2026-10-18: 당뇨 인슐린·당뇨발에 "일반식 드시고 계심"
        elif "htn" in hist and rng.random() < 0.2:
            form["diet"] = "lowsalt"
        else:
            form["diet"] = "gd"
    if "appetite" in form:
        form["appetite"] = "poor" if nausea or (tox and rng.random() < 0.5) else ("poor" if rng.random() < 0.15 else "good")
    if "dysphagia" in form:
        form["dysphagia"] = (sc is not None and sc.key == "Tracheostomy" or "후두" in patient.diagnosis) and rng.random() < 0.3   # not ESS (2026-10-18)
    if "bowel" in form:
        form["bowel"] = "diarrhea" if (tox and "설사" in cc) else rng.choices(["normal", "constipation"], weights=[88, 12] if age >= 60 else [95, 5])[0]
    if "voiding" in form and form.get("voiding") == "foley":
        form["voiding"] = "normal"
    if "voiding" in form and age < 60 and rng.random() < 0.92:
        form["voiding"] = "normal"
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
        else:
            site = next((s for w, s in _SITE_BY_WORD if w in cc), None)
            form["pain_site"] = site or ("복부" if chemo else {"산부인과": "하복부", "비뇨의학과": "하복부", "이비인후과": "목", "유방외과": "유방"}.get(
                patient.department, "복부"))   # a body part, not "수술 예정 부위" (2026-10-18)
    if "emotion" in form:
        form["emotion"] = ["anxiety"] if rng.random() < (0.3 if not chemo else 0.15) else ["none"]
    if "symptom_screen" in form:
        edema_ok = any(h in hist for h in ("heart", "ckd")) or patient.department == "정형외과"
        form["symptom_screen"] = "pos" if edema_ok and rng.random() < 0.4 else "neg"
        if form["symptom_screen"] == "neg":
            form.pop("symptom_note", None)
        if re.search(r"숨|호흡곤란|부종|두근", cc):   # the complaint already says it: no "숨찬 건 없으세요? — 그런 건 없어요"
            form.pop("symptom_screen", None)
            form.pop("symptom_note", None)
    if "weakness" in form:
        weak = "stroke" in hist or (patient.department == "정형외과" and rng.random() < 0.3)
        form["weakness"] = "pos" if weak and rng.random() < 0.7 else "neg"
        if form["weakness"] == "pos":
            form["weakness_note"] = ("환측 팔" if _upper_limb(patient.diagnosis) else "환측 다리") if patient.department == "정형외과" else rng.choice(["오른쪽 다리", "왼쪽 팔"])
            if "stroke" in hist and "뇌경색, 후유증 없음" in form.get("history_detail", ""):
                side = form["weakness_note"].split()[0] if form["weakness_note"].split()[0] in ("오른쪽", "왼쪽") else ""
                form["history_detail"] = form["history_detail"].replace("뇌경색, 후유증 없음", f"뇌경색, {side + ' ' if side else ''}편마비 후유증 있음")
        else:
            form.pop("weakness_note", None)
    if "social_work" in form and rng.random() < 0.95:
        form["social_work"] = "neg"
    if "fall_history" in form:   # the fall that brought the patient in counts (user 2026-10-17)
        fell = bool(re.search(r"낙상|미끄러|넘어", cc)) or ("골절" in cc and not re.search(r"사고|축구|자전거", cc))   # a crash is not a fall
        form["fall_history"] = "yes" if fell or (age >= 75 and rng.random() < 0.08) else "no"
    # an elective admission is awake; confusion only in the very old after a fall
    if "consciousness" in form:
        form["consciousness"] = "confuse" if (age >= 75 and any(w in cc for w in ("낙상", "골절", "미끄러")) and rng.random() < 0.15) else "alert"
    if "isolation" in form:
        form["isolation"] = "contact" if rng.random() < 0.05 else "none"
    if "devices" in form and not chemo and not any(w in cc for w in ("장루", "회장루")):
        form.pop("devices")                  # a THA patient does not come in with a stoma or a PICC
    if not chemo and (re.search(r"회장루|장루", cc) or (sc is not None and sc.key == "Ileostomy repair")):   # stoma reversal: the stoma is still there
        form["devices"] = "회장루" if "회장루" in cc else "장루"
        if "bowel" in form:
            form["bowel"] = "stoma"
    if "bowel" in form and "변실금" in cc:
        form["bowel"] = "incontinence"
    if "allergy" in form:
        form["allergy"] = ["none"] if rng.random() < 0.8 else [rng.choices(["food", "penicillin", "antibiotic", "nsaid", "contrast"], weights=[4, 3, 2, 2, 1])[0]]   # no "기타 알러지"
        form["allergy_food"] = rng.choice(["새우", "복숭아", "땅콩", "갑각류", "계란"])   # "음식 알레르기 있으십니다" never named the food (2026-10-18)
    if "sense" in form:
        p_none = 0.65 if age >= 65 else 0.85
        form["sense"] = ["none"] if rng.random() < p_none else [rng.choices(["hearing", "vision", "speech", "foreign"], weights=[55, 40, 3, 2])[0]]
    if "mobility" in form and patient.department == "정형외과":   # 2026-10-18: 47세 회전근개 "워커 짚고", 갓 다친 하지 골절이 걸어서 옴
        if _upper_limb(patient.diagnosis):
            form["mobility"] = "independent"
        elif re.search(r"골절|미끄러|넘어|낙상|압궤", cc):
            form["mobility"] = rng.choice(["bedrest", "assist"])
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
            months = max(1, round((patient.cycle or 1) * (14 if "FOLF" in (patient.regimen or "") else 21) / 30) + 1)   # adjuvant cycle 7 ≠ "1개월 전 수술"
            form["past_surgery"] = f"{months}개월 전 {treat + ' ' if treat else ''}수술"
        elif not chemo and sc is not None and sc.key == "Breast reconstruction" and re.search(r"지연|확장기|보형물|전절제 후", cc):
            form["past_surgery"] = f"{rng.randint(1, 3)}년 전 유방 전절제술" + (" 및 조직확장기 삽입" if "확장기" in cc else "")
        elif not chemo and "갑상선 전절제 후" in cc:
            form["past_surgery"] = f"{rng.randint(1, 5)}년 전 갑상선 전절제술"
        elif not chemo and sc is not None and sc.key == "Ileostomy repair":
            m = re.search(r"(\d+)개월", form.get("present_illness", ""))   # "회장루 조성 6개월 경과" ↔ "N개월 전 … 회장루 조성술"
            form["past_surgery"] = f"{m.group(1) if m else rng.randint(4, 8)}개월 전 직장암으로 저위전방절제술 및 회장루 조성술"
        elif not chemo and re.search(r"반복 제왕|이전 제왕", cc):
            form["past_surgery"] = f"{rng.randint(2, 5)}년 전 제왕절개"
        elif rng.random() < 0.45:
            form.pop("past_surgery", None)
        else:
            form["past_surgery"] = rng.choice(cands)
    if "intake_screen" in form:
        form["intake_screen"] = "decreased" if form.get("appetite") == "poor" else ("special" if rng.random() < 0.2 else "neg")
        if form["intake_screen"] != "special":
            form.pop("intake_note", None)
    if "depression_screen" in form:
        # 정서평가 (user 2026-10-17): the 2-week day counts follow whether the patient is worried about the admission
        worried = any(e in (form.get("emotion") or []) for e in ("anxiety", "depression"))
        form["mood_days"] = rng.choices(["none", "few", "week", "daily"], weights=[25, 50, 15, 10])[0] if worried else rng.choices(["none", "few"], weights=[9, 1])[0]
        form["interest_days"] = rng.choices(["none", "few", "week", "daily"], weights=[45, 35, 12, 8])[0] if worried else "none"
        form["depression_screen"] = "pos" if form["mood_days"] in ("week", "daily") or form["interest_days"] in ("week", "daily") else "neg"
        _days = {"none": "없다고", "few": "며칠 있다고", "week": "일주일 넘게 있다고", "daily": "거의 매일 있다고"}
        form["mood_summary"] = f"기분 가라앉은 날이 {_days[form['mood_days']].replace('다고', '고') if form['mood_days'] != 'none' else '없고'} 흥미 떨어진 날은 {_days[form['interest_days']]}"
        if "selfharm" in form and form["depression_screen"] == "neg":
            form["selfharm"] = "none"
    # habits by sex and age (2026-10-18 검수: 여성 현재 흡연 24%·과거 흡연 53%, 임신부 흡연)
    female = patient.sex.startswith("여")
    pregnant = patient.surgery == "C-sec"
    if "smoking" in form:
        form["smoking"] = "never" if pregnant else rng.choices(["never", "quit", "current"],
                                                            weights=[88, 8, 4] if female else ([45, 40, 15] if age >= 70 else [40, 35, 25]))[0]
    if "alcohol" in form:
        form["alcohol"] = "none" if pregnant else rng.choices(["none", "social", "heavy"], weights=[60, 38, 2] if female else [35, 55, 10])[0]
    # 금연·금주 교육은 해당 환자에게만 (user 2026-10-17); set unconditionally so the bool never lags the habit field
    form["smoking_edu"] = form.get("smoking") == "current"
    form["alcohol_edu"] = form.get("alcohol") in ("social", "heavy")
    if "height" in form or "weight" in form:
        # 2026-10-17: "150 cm, 43 kg" for a 64-year-old man, "164 cm, 92 kg, BMI 20.2" — sex-aware build, BMI from the numbers
        male = patient.sex.startswith("남")
        h = rng.randint(162, 182) if male else rng.randint(150, 168)
        if age >= 70:
            h -= rng.randint(2, 5)
        bmi = rng.uniform(19.0, 29.0) if not (chemo or "체중" in cc) else rng.uniform(17.5, 24.0)
        form["height"], form["weight"] = h, int(round(bmi * (h / 100) ** 2))
        form["bmi"] = round(form["weight"] / (h / 100) ** 2, 1)
    if "marital" in form:
        if age < 30:
            form["marital"] = rng.choices(["single", "married"], weights=[75, 25])[0]
        elif age < 60:
            form["marital"] = rng.choices(["married", "single", "other"], weights=[80, 12, 8])[0]
        else:
            form["marital"] = rng.choices(["married", "other", "single"], weights=[70, 25, 5])[0]
    if "weight_screen" in form:
        cancer = any(w in cc for w in ("암", "종양", "전이")) or chemo
        form["weight_screen"] = "loss" if (cancer and rng.random() < 0.3) else ("gain" if rng.random() < 0.08 else "neg")
        # the amount follows the direction (2026-10-18: "2kg 증가" sent to 영양 상담 as weight loss)
        if form["weight_screen"] == "loss":
            form["weight_change"] = rng.choice(["5kg 감소", "3kg 감소", "4kg 정도 감소"])   # "지난 한 달간 체중 2개월간 5kg 감소" (2026-10-18)
        elif form["weight_screen"] == "gain":
            form["weight_change"] = rng.choice(["2kg 증가", "3kg 증가"])
        else:
            form.pop("weight_change", None)
    if form.get("sleep") == "hypnotic":
        if age < 55:
            form["sleep"] = "good"
        elif "졸피뎀" not in str(form.get("medications") or ""):
            meds = [m for m in str(form.get("medications") or "").split(", ") if m and m != "복용 중인 약 없음"]
            form["medications"] = ", ".join(meds + ["졸피뎀 5mg hs"])
    # caregiver like the handover (2026-10-18 검수: 83% "보호자 없음" because the random fill treated "none" as normal)
    if "caregiver" in form:
        allowed = list(sc.form.get("caregiver") or []) if sc is not None else []
        if age < 20:
            form["caregiver"] = "parent"
        elif allowed:
            form["caregiver"] = rng.choice(allowed)
        elif patient.surgery == "C-sec":
            form["caregiver"] = "spouse"
        elif age >= 70:
            form["caregiver"] = rng.choices(["spouse", "child", "caregiver", "intermittent"], weights=[35, 35, 20, 10])[0]
        else:
            form["caregiver"] = rng.choices(["spouse", "child", "none", "intermittent", "caregiver"], weights=[45, 10 if age >= 45 else 0, 30, 12, 3])[0]
        if form["caregiver"] == "spouse" and form.get("marital") in ("single", "other"):
            form["marital"] = "married"            # a spouse at the bedside: not "사별하셨고"
        elif form["caregiver"] == "child" and form.get("marital") == "single":
            form["marital"] = "other"              # "아직이요" + "딸이 와 있을 거예요" (2026-10-18)
    if "알레르기" in str(form.get("intake_note") or "") and form.get("allergy") in (None, ["none"]):
        form["allergy"] = ["food"]                 # "알레르기 없습니다" + "해산물 알레르기라고 하셔서"
        form.setdefault("allergy_reaction", "두드러기")
        m = re.search(r"(\S+) 알레르기", str(form.get("intake_note") or ""))
        form["allergy_food"] = m.group(1) if m else form.get("allergy_food", "해산물")


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
        probs.append("knowledge")
    # 불안 only when the patient said so (2026-10-17: "별로 걱정은 안 돼요" followed by 간호 문제 "불안")
    if any(e in (form.get("emotion") or []) for e in ("anxiety", "depression")):
        probs.insert(0, "anxiety")
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


# ---------------------------------------------------------------------------
# S2 · S3-1 · S3-2 · S4 · S5 · S6: derived from the patient the way S1 is (2026-10-17 audit, ≥10 scripts per template)
# ---------------------------------------------------------------------------

_UPPER_LIMB = ("손목", "요골", "쇄골", "상완골", "어깨", "견관절", "회전근개")


def _upper_limb(dx: str) -> bool:
    return any(w in dx for w in _UPPER_LIMB)


def _off_operated_side(patient: Patient, sites: list[str], text: str = "") -> list[str]:
    """IV sites away from a breast or upper-limb operation (its own teaching forbids the operated arm);
    S3-1, S5 and S6 all draw their line through this (2026-10-18: 우측 회전근개 봉합 + "오른팔 22G line").
    ``text`` (the wound line) names the side when the diagnosis does not."""
    dx = patient.diagnosis or ""
    side = next((s for s in ("우측", "좌측") if s in dx), "") or next((s for s in ("우측", "좌측") if s in text), "")
    if not side or not (patient.department == "유방외과" or "유방" in dx or _upper_limb(dx)):
        return sites
    bad = ("Rt", "오른") if side == "우측" else ("Lt", "왼")
    return [x for x in sites if not x.startswith(bad)] or sites


def _clock(minutes: int) -> str:
    """Minutes since midnight -> '오후 2시 30분' (ward clock: 새벽 0~5, 오전 6~11, 오후 12~23)."""
    h, m = divmod(minutes % (24 * 60), 60)
    pre = "새벽" if h < 6 else "오전" if h < 12 else "오후"
    h12 = 12 if h == 0 else h if h <= 12 else h - 12
    return f"{pre} {h12}시" + (f" {m}분" if m else "")


def _pool(sc, key: str, tkey: str) -> list[str]:
    """Scenario pool ("s5.special" beats "special") falling back to the generic text pools."""
    pools = sc.pools if sc else {}
    return list(pools.get(f"{tkey}.{key}") or pools.get(key) or TEXT_POOLS.get(f"{tkey}.{key}") or TEXT_POOLS.get(key) or [])


_EMPTY = ("", "없음", "배액관 없음", "항생제 없음", "특이사항 없음", "특이 소견 없음", "변화 없음")


def _pick(rng: random.Random, patient: Patient, sc, key: str, tkey: str) -> str:
    pool = [x for x in _pool(sc, key, tkey) if x not in _EMPTY]
    pool = coherent_pool(patient.diagnosis, tuple(pool), trauma=False, sex=patient.sex) or pool
    return _fill(rng.choice(pool), patient, sc) if pool else ""


def _scenario_drains(sc) -> list[str]:
    return [x for x in ((sc.form.get("s3_1.drain") if sc else None) or ["none"]) if x != "none"]


def _drain_text(rng: random.Random, patient: Patient, sc, tkey: str) -> str:
    """'JP serosanguineous 40cc' for a patient whose surgery actually leaves a drain, else ''."""
    if patient.kind == "chemo" or not _scenario_drains(sc):
        return ""
    pool = [x for x in _pool(sc, "drain", tkey) if x not in _EMPTY] if (sc.pools.get(f"{tkey}.drain") or sc.pools.get("drain")) else []
    if (patient.pod or 0) == 0:   # the drain came up with the patient today (2026-10-18: POD 0 "Hemovac 어제 제거", "양 줄고 있음")
        pool = [x for x in pool if not re.search(r"어제|줄|제거|옅어|\bserous\b", x)]   # and still bloody/serosanguineous
    elif (patient.pod or 0) == 1:
        pool = [x for x in pool if "어제 제거" not in x]
    pool = coherent_pool(patient.diagnosis, tuple(pool), trauma=False, sex=patient.sex) or pool
    if pool:
        return _fill(rng.choice(pool), patient, sc)
    kind = "Hemovac" if patient.department == "정형외과" else "JP"
    color = "bloody" if (patient.pod or 0) == 0 else rng.choice(["serosanguineous", "serosanguineous", "serous"])
    return f"{kind} 배액 {color} 양상 {rng.randrange(10, 90, 5)}cc"


def _derive_s2(form: dict[str, Any], patient: Patient, sc, rng: random.Random) -> None:
    """Pre-op education: surgery time follows the order, drugs follow the age, prep follows the surgery."""
    age = patient.age or 50
    order = rng.choices(["first", "second", "third", "unknown"], weights=[50, 25, 15, 10])[0]
    form["order"] = order
    slot = {"first": ["오전 8시", "오전 8시 30분"], "second": ["오전 10시 30분", "오전 11시"],
            "third": ["오후 1시", "오후 2시", "오후 3시"], "unknown": [""]}[order]
    form["op_date"] = f"내일 {patient.op_date} {rng.choice(slot)}".strip()   # S2 is dictated the day before (admission = op - 1)
    form["npo_start"] = rng.choices(["midnight", "mn_solid_water2", "evening"], weights=[65, 25, 10])[0]
    old = age >= 50
    form["bp_med"] = rng.choices(["take_am", "hold"], weights=[8, 2])[0] if old and rng.random() < 0.45 else "na"
    form["dm_med"] = rng.choices(["hold_evening", "hold_am", "insulin_half"], weights=[6, 3, 1])[0] if old and rng.random() < 0.3 else "na"
    form["anticoag"] = rng.choices(["stopped", "hold_today", "bridging"], weights=[7, 2, 1])[0] if age >= 60 and rng.random() < 0.25 else "na"
    if form["bp_med"] == "take_am" or age < 40 or rng.random() < 0.85:
        form.pop("npo_meds", None)        # the 혈압약 sentence already says what may be taken with water
    else:
        form["npo_meds"] = "갑상선약은 아침 소량의 물로"
    form.pop("prep_detail", None)         # the 전처치 item already reads "저녁 8시 하제 복용 예정"
    big = (sc.los[1] if sc else 5) >= 4
    form["consents"] = ["op", "anes"] + (["tf"] if rng.random() < (0.7 if big else 0.2) else [])
    lateral = bool(re.search(r"우측|좌측", patient.diagnosis) and not re.search(r"대장|결장", patient.diagnosis)) or \
        patient.department == "정형외과" or "유방" in patient.diagnosis or \
        (sc is not None and sc.key == "Hernioplasty")   # "양측 성대·갑상선·난소" is not a site to mark
    if lateral:
        form["marking"] = rng.random() < 0.95
    else:
        form.pop("marking", None)
    rem = [x for x in ("glasses", "jewelry", "nail") if rng.random() < 0.6]
    if age >= 60 and rng.random() < 0.5:
        rem.append("denture")
    if age >= 70 and rng.random() < 0.15:
        rem.append("hearing")
    if rng.random() < 0.2:
        rem.append("underwear")
    form["removables"] = rem or ["jewelry"]
    icu = sc is not None and sc.key in ("Tracheostomy", "Staging laparotomy", "MRND") and rng.random() < 0.2
    form["after_route"] = "icu" if icu else "rr"
    form["waiting"] = "absent" if rng.random() < 0.15 else "done"
    # nobody "환자분과 보호자분 모두 이해" when the guardian is not there (2026-10-18)
    form["understanding"] = rng.choices(["patient", "re_edu"], weights=[9, 1])[0] if form["waiting"] == "absent" else \
        rng.choices(["both", "patient", "re_edu"], weights=[70, 25, 5])[0]
    abdominal = sc is not None and sc.form.get("abdomen", 1) is not None
    qs = [q for q in TEXT_POOLS["question"] if (abdominal or "가스" not in q) and ("PCA" not in q or "pca" in (form.get("attachments") or []))
          and ("걸을 수 있는지" not in q or (sc is None or sc.key != "BKA") and not form.get("ambulation"))]   # no answer that contradicts the plan
    if rng.random() < 0.7:
        form["question"] = rng.choice(qs)
    else:
        form.pop("question", None)
    if sc is not None and sc.key == "BKA":
        form["ambulation"], form["leg"] = False, False
    if sc is not None and sc.key == "Tracheostomy":
        form["inspirometer"] = False             # useless through a tracheostomy
        form["question"] = "수술 후 말할 수 있는지 질문하여 기관절개관 때문에 당분간 말하기 어려워 필담판으로 의사소통한다고 설명함"
    drains = (sc.form.get("s3_1.drain") if sc else None) or ["none"]
    if "none" not in drains:                     # the surgery always leaves a drain: say it before (2026-10-18: TM c ALND without JP)
        kind = "hemovac" if any("hemovac" in d for d in drains) else "jp"
        att = list(form.get("attachments") or [])
        if kind not in att:
            form["attachments"] = [kind] + att


def _derive_s3_1(form: dict[str, Any], patient: Patient, sc, rng: random.Random) -> None:
    """Immediate post-op record = POD 0, right after the patient comes up from the recovery room (user 2026-10-17:
    "수술 후 기록은 POD#0 수술 나왔을 때 바로 하는 기록"); the next days belong to the progress record (S6)."""
    pod = 0
    patient.pod = pod
    day0 = pod == 0
    form["timing"] = {0: "day0", 1: "pod1", 2: "pod2"}[pod]
    if day0:
        form["arrival_time"] = rng.choice(TEXT_POOLS["arrival_time"])
        form["vs_lead"] = rng.choice(["도착 당시", "올라오신 직후", "도착 직후"])   # "병실 도착" is said once, in the arrival sentence
    else:
        form.pop("arrival_time", None)
        form["vs_lead"] = rng.choice(["오전 9시", "오전 10시 30분", "오후 2시", "오후 6시"])
    form["consciousness"] = "drowsy" if day0 and rng.random() < 0.2 else "alert"
    form["responds"] = False if form["consciousness"] == "drowsy" else rng.random() < 0.8
    form["nausea"] = rng.choices(["none", "nausea", "vomit"], weights=[70, 25, 5] if day0 else [92, 8, 0])[0]
    v = random_vitals(rng, "normal", with_spo2=True)
    v["spo2"] = v["spo2"] or rng.randint(95, 99)
    minor = (sc.los[1] if sc else 5) <= 3
    o2 = "nasal" if (day0 and rng.random() < (0.25 if minor else 0.6)) or (not day0 and rng.random() < 0.08) else "none"
    forced = (sc.form.get("s3_1.o2") or sc.form.get("o2")) if sc else None
    if forced and o2 not in forced:
        o2 = forced[0]
    if sc is not None and sc.key == "Tracheostomy":
        o2 = "trach"
    form["o2"] = o2
    v["o2"] = {"none": "room air", "nasal": rng.choice(["O2 2L nasal", "O2 3L nasal"]), "mask": "O2 5L mask", "trach": "trach mask 5L"}[o2]
    if rng.random() < 0.1:
        v["bt"] = round(rng.uniform(37.6, 37.9), 1)   # low-grade post-op warmth; 38+ would need a noti line (2026-10-18)
    if sc is not None and sc.key == "Tracheostomy":
        v["o2"] = "trach mask 5L"                     # humidified O2 through the stoma, not a face mask
    form["vitals"] = v
    form["nrs"] = rng.randint(*{0: (3, 6), 1: (2, 5), 2: (1, 4)}[pod])
    if form.get("pain_med") == "none":
        form["nrs"] = min(form["nrs"], 2)
    if pod >= 2 and minor and form.get("pain_med") in ("pca", "prn_iv"):
        form["pain_med"] = rng.choice(["prn_po", "regular"])     # a 2-day surgery is on tablets by POD 2
    pca_ok = sc is not None and any("pca" in a for a in (sc.form.get("attachments") or []))
    if form.get("pain_med") == "pca" and not pca_ok:
        form["pain_med"] = "prn_iv" if form["nrs"] >= 4 else "regular"   # 기관절개·ESS·TURB … come up without a PCA (2026-10-18 2차 검수)
    if day0 and form.get("pain_med") == "prn_po":
        form["pain_med"] = "prn_iv"           # nothing by mouth an hour after the OR
    if form["nrs"] >= 5 and form.get("pain_med") in ("regular", "prn_po"):
        form["pain_med"] = "prn_iv"           # NRS 5-6 on 정규 진통제 alone is not charted without a PRN
    form["pca_edu"] = form.get("pain_med") == "pca" and day0 and form["consciousness"] == "alert"
    form["breathing"] = "intensive" if day0 else "inspirometer"
    if not day0:
        form["hob"] = "30"
    # catheter: out by POD 1 unless this surgery keeps it (RALRP); the special education must agree
    keep_only = sc is not None and set(sc.form.get("foley") or []) == {"keep"}
    if not day0 and form.get("foley") == "keep" and not keep_only:
        form["foley"] = rng.choice(["removed", "none"])
    allowed_foley = list(sc.form.get("s3_1.foley") or sc.form.get("foley") or []) if sc is not None else []
    if day0 and "keep" in allowed_foley:
        form["foley"] = "keep"            # C-sec, TURB, LAR, TAH … come up with their catheter (2026-10-18: half arrived "소변줄 없이")
    elif day0 and form.get("foley") == "removed":
        form["foley"] = "none"            # "소변줄 제거하고 자가배뇨 확인" minutes after the ward arrival is not a POD 0 fact
    if form.get("foley") != "keep" and any(w in form.get("special_edu", "") for w in ("소변줄", "세척", "방광 내")):
        alt = [x for x in _pool(sc, "special_edu", "s3_1") if not any(w in x for w in ("소변줄", "세척", "방광 내"))]
        if alt:
            form["special_edu"] = rng.choice(alt)
        else:
            form.pop("special_edu", None)
    # --- 범주 재편 (user 2026-10-17): the surgery-specific item goes to its category; observation and management stay apart
    sp = str(form.get("special_edu") or "")
    if sp and re.search(r"소변줄|소변백|방광|자가배뇨", sp):
        form["foley_note"], sp = sp, ""
    elif sp and re.search(r"배액|JP|Hemovac|헤모박|음압|우윳빛", sp):
        form["drain_note"], sp = sp, ""
    elif sp and re.search(r"알리도록|알리시|즉시 알|호출벨", sp):
        form["report_note"], sp = sp, ""
    if sp:
        form["special_edu"] = sp
    else:
        form.pop("special_edu", None)
    has_drain = form.get("drain") not in (None, "", "none")
    form["drain_edu"] = has_drain and rng.random() < 0.9
    if form.get("drain_note") and re.search(r"당겨|양 (늘|증가)|색 짙", form["drain_note"]):
        form["drain_edu"] = False                               # the surgery-specific line already says it
    if not has_drain:
        form.pop("drain_note", None)
    if keep_only and form.get("foley") == "keep" and not re.search(r"1~2주|외래에서 제거", form.get("foley_note") or ""):
        long = [x for x in _pool(sc, "special_edu", "s3_1") if "1~2주" in x or "외래에서 제거" in x]
        line = long[0] if long else "소변줄은 1~2주 유지 후 외래에서 제거 예정이며 고정 상태 잘 유지하도록 교육함"
        form["foley_note"] = f"{line}. {form['foley_note']}" if form.get("foley_note") else line   # RALRP: how long it stays
    form["foley_edu"] = form.get("foley") == "keep" and rng.random() < 0.9
    if sc is not None and sc.key in ("TURB", "LAR") and form.get("foley") == "keep":
        form["foley_edu"] = False         # "소변줄은 다음날 아침 제거 예정" is wrong on CBI / after LAR
        form.setdefault("foley_note", "소변 색 짙어지거나 덩어리 나오면 즉시 알리도록 교육함" if sc.key == "TURB"
                        else "소변줄은 배뇨 기능 회복 확인 후 수일 내 제거 예정임")
    if form.get("foley_note") and re.search(r"당겨|소변백|제거 예정|관리", form["foley_note"]):
        form["foley_edu"] = False         # the surgery's own line says it (RALRP: "1~2주 유지 후 외래에서 제거", not "내일 아침")
    if form.get("foley") != "keep":
        form.pop("foley_note", None)
    # 약물 투여: what actually went in after the operation
    meds = []
    if rng.random() < 0.85:
        meds.append(rng.choice(["예방적 항생제 세파졸린 1g IV", "세파졸린 1g IV", "세프트리악손 2g IV"]))
    if form.get("nausea") in ("nausea", "vomit"):
        meds.append(rng.choice(["온단세트론 4mg IV", "메토클로프라미드 10mg IV"]))
    if sc is not None and (sc.key in ("TKA", "THA", "BKA") or (sc.key == "ORIF" and not _upper_limb(patient.diagnosis))):
        meds.append("에녹사파린 40mg 피하 주사")   # VTE prophylaxis after major lower-limb surgery, not after an arthroscopy
    if len(meds) > 1:
        meds = [m.replace("예방적 항생제 ", "") for m in meds]   # the prefix read as if every drug were an antibiotic
    if meds:
        form["meds_given"] = ", ".join(meds)
    else:
        form.pop("meds_given", None)
    # 수술 후 처치: by the kind of operation
    key = sc.key if sc is not None else ""
    if key in ("TKA", "THA", "ORIF", "Meniscectomy", "Meniscal repair"):
        care = ["ipc", "icebag"] if key in ("TKA", "THA") else ["icebag"]
    elif key in ("TSA", "Rotator cuff repair", "ESS"):
        care = ["icebag"]
    elif key == "BKA":
        care = ["elevation", "compression"]
    elif key == "Breast reconstruction":
        care = []                          # a flap or implant must not be compressed (its own teaching says so)
    elif patient.department == "유방외과" or "mastectomy" in key.lower() or "Breast" in key:
        care = ["compression"]
    else:
        care = ["warming"] if rng.random() < 0.3 and float(v.get("bt") or 36.5) < 37.6 else []   # no warming blanket on a warm patient
    if key == "ESS":
        care = ["icebag_nose"]
    form["postop_care"] = care
    abdominal_open = sc is not None and sc.form.get("abdomen", 1) is not None and sc.los[1] >= 4
    if day0 and abdominal_open and form.get("diet_status") in ("sow", "ld", "gd"):
        form["diet_status"] = "npo"       # nobody drinks on the evening of a colon/uterus operation
    # the diet line follows the patient (2026-10-18: "식이 제한 없이 일반식" to a vomiting or drowsy patient; gas-based NPO for a tracheostomy)
    if day0 and form.get("diet_status") in ("sow", "ld", "gd"):
        if form.get("nausea") in ("nausea", "vomit"):
            form["diet_status"] = "npo_nausea"
        elif form["consciousness"] == "drowsy":
            form["diet_status"] = "npo_drowsy"
    if key == "Tracheostomy" and form.get("diet_status") in ("npo", "ld", "sow", "gd"):
        form["diet_status"] = "npo_trach"
    if day0 and form.get("abdomen") == "gas_out":
        form["abdomen"] = "soft"          # no flatus an hour after the OR
    if day0 and form.get("pain_med") == "prn_po" and (form.get("nausea") in ("nausea", "vomit") or form["consciousness"] == "drowsy"):
        form["pain_med"] = "prn_iv"
    if form.get("pain_med") == "prn_iv":
        form["nrs"] = max(form["nrs"], 4)  # "아파하셔서 PRN" at NRS 3
    forced_walk = sc is not None and (sc.form.get("ambulation_plan") or []) == ["walk_today"]
    if day0 and form.get("ambulation_plan") == "walk_today" and not forced_walk:
        form["ambulation_plan"] = rng.choice(["evening_sit", "bedrest"])
    elif forced_walk:
        form["ambulation_plan"] = "walk_today"   # arthroscopy walks the same day (its own pool says so)
    if day0 and sc is not None and sc.key in ("BKA", "ORIF") and not _upper_limb(patient.diagnosis):
        form["ambulation_plan"] = "bedrest"
    if not day0:
        form["ambulation_plan"] = "bedrest" if (sc is not None and sc.key == "BKA") else "walk_today"
    lower = (patient.department == "정형외과" and not _upper_limb(patient.diagnosis)) or \
            (sc is not None and sc.key in ("TURB", "C-sec", "Hernioplasty", "Hemorrhoidectomy", "Rectal prolapse OP"))   # spinal only, not RALRP/nephrectomy
    if lower:
        form["leg_check"] = rng.random() < 0.8     # spinal anaesthesia / lower-limb surgery
    else:
        form.pop("leg_check", None)
    form["leg_exercise"] = rng.random() < (0.3 if _upper_limb(patient.diagnosis) else 0.7)
    if sc is not None and sc.key == "BKA":
        form["leg_exercise"] = False
        form.pop("leg_check", None)
    form["fall_edu"] = rng.random() < 0.6
    if "dressing" in form:
        form["dressing"] = rng.choices(["clean", "oozing", "bleeding"], weights=[85, 12, 3])[0]
    form["report_edu"] = rng.random() < 0.8
    if "dressing" not in form and form["report_edu"]:   # TURB/ESS: no dressing to soak (2026-10-18: "드레싱 젖거나 피 비칠 때")
        form["report_edu"] = False
        form.setdefault("report_note", "38도 이상 발열, 숨참, 심한 통증, 출혈 있으면 바로 호출하도록 교육함")
    if form.get("dressing") == "bleeding" and "에녹사파린" in str(form.get("meds_given") or ""):
        form["meds_given"] = ", ".join(m for m in form["meds_given"].split(", ") if "에녹사파린" not in m)   # no LMWH right after a bleeding noti
        if not form["meds_given"]:
            form.pop("meds_given")
    form["understanding"] = "caregiver" if form["consciousness"] == "drowsy" else rng.choices(["both", "patient", "re_edu"], weights=[70, 25, 5])[0]
    if "drain_amount" in form:
        hi_amt = 150 if patient.department == "정형외과" else 90
        form["drain_amount"] = rng.randint(10, 60) if day0 else rng.randint(20, hi_amt)
        if key in ("Bilateral total thyroidectomy", "MRND"):
            form["drain_amount"] = rng.randint(5, 30)   # a neck drain at 60cc would be a noti
    # IV on the other arm after breast or shoulder surgery (its own teaching forbids the operated side)
    ok_iv = _off_operated_side(patient, TEXT_POOLS["iv"])
    if "iv" in form and form["iv"] not in ok_iv:
        form["iv"] = rng.choice(ok_iv)
    if key == "Tracheostomy":   # a fresh cuffed tracheostomy cannot speak, and blows into no spirometer
        form["responds"] = False
        form.pop("breathing", None)
        said = " ".join(str(form.get(k) or "") for k in ("special_edu", "report_note", "drain_note"))
        if "필담" not in said:   # the record says how this patient talks to us (2026-10-18: 74% had no 필담 line)
            form["report_note"] = "필담판과 호출벨 손 닿는 곳에 두고 숨차거나 이상 있으면 바로 호출벨 누르도록 교육함"
            form["report_edu"] = False        # one call-bell sentence, not two
    # the same teaching twice (ice bag + 냉찜질, IPC/항응고 + 혈전 예방, 거상·압박, 침상 머리, 가스 배출 후 식이)
    sp = str(form.get("special_edu") or "")
    clash = [(r"냉찜질|얼음찜질|ice", any(c.startswith("icebag") for c in care)), (r"IPC|항응고|혈전 예방", "에녹사파린" in str(form.get("meds_given") or "") or "ipc" in care),
             (r"거상|압박 드레싱", "elevation" in care or "compression" in care), (r"침상 머리", form.get("hob") in ("30", "semi")),
             (r"가스 배출", str(form.get("diet_status") or "").startswith("npo")),
             (r"발목 운동|발목 펌프", bool(form.get("leg_exercise"))), (r"침상 안정", bool(form.get("ambulation_plan")))]   # 2026-10-18 2차 검수
    if sp and any(on and re.search(pat, sp) for pat, on in clash):
        alt = [x for x in _pool(sc, "special_edu", "s3_1") if not any(on and re.search(pat, x) for pat, on in clash)
               and not re.search(r"소변줄|소변백|방광|자가배뇨|배액|JP|Hemovac|헤모박|알리도록|알리시|호출벨", x)]
        if alt:
            form["special_edu"] = _fill(rng.choice(alt), patient, sc)
        else:
            form.pop("special_edu", None)
    form["exam_care"] = "na"
    if key == "TURB" and form.get("foley") == "keep":
        form["foley"] = "cbi"                 # continuous irrigation runs through a 3-way catheter, and the urine is pink
        for k in ("special_edu", "foley_note"):   # irrigation running ≠ catheter clamped for an intravesical instillation (2026-10-18)
            if "잠근" in str(form.get(k) or ""):
                form.pop(k)


def _ev(**kw: Any) -> dict[str, Any]:
    return kw


# One coherent story per event: vitals profile, what the patient says, the finding that explains it, the
# judgement, the SBAR tail (prefixed with the actual vitals), the order set, the drug, nursing actions,
# tests sent and the follow-up plan.  Several variants per event keep the recordings varied.
_EVENTS: dict[str, list[dict[str, Any]]] = {
    "발열": [
        _ev(vs="fever", complaint=["열감 조금 있다고 표현하고 오한은 없음", "몸이 으슬으슬하고 열감 있다고 함"], lung=["decreased"],
            judgement=["수술 후 폐 확장 저하에 의한 발열 가능성", "무기폐에 의한 발열 가능성"],
            tail=["수술 부위 oozing 없고 폐음 하부 감소되어 있으며 심호흡 잘 안 되는 상태", "수술 부위 특이 소견 없고 폐 하부 호흡음 감소된 상태"],
            orders=["acetaminophen 1g IV 1회 투여, lung care 및 ambulation 격려, chest PA 촬영 후 결과 노티", "acetaminophen 650mg PO, 심호흡과 inspirometer 격려, chest PA 촬영"],
            med=["{t} PRN acetaminophen 1g/100mL IV 30분간 점적", "{t} acetaminophen 650mg PO"],
            nursing=[["breathing", "inspirometer", "ambulation"], ["breathing", "inspirometer"]],
            exam=["chest PA 촬영 위해 목걸이와 환의 금속 단추 제거 후 도보로 영상의학과 이송함", ""],
            plan=["chest PA 결과 판독 확인 후 주치의 노티 예정이며 4시간 간격으로 체온 추적 관찰", "4시간 간격으로 체온 추적하고 심호흡 격려 지속"]),
        _ev(vs="fever", complaint=["오한 있다고 함", "오한 동반한 열감 호소함"], wound=["redness"], lung=["clear"],
            judgement=["수술 부위 감염 가능성"], tail=["오한 동반되고 수술 부위 발적과 열감 있는 상태"],
            orders=["blood culture 2쌍, wound culture 시행 후 acetaminophen 1g IV, 드레싱 교환", "배양 검사 후 acetaminophen 1g IV 1회, 항생제 처방 확인"],
            med=["{t} PRN acetaminophen 1g/100mL IV 30분간 점적", "{t} PRN acetaminophen 1g IV"], nursing=[["tepid", "hydration"], ["blanket"]],
            exam=["blood culture 2쌍 채혈하고 wound culture 검체 검사실로 보냄"],
            plan=["배양 결과 확인 예정이며 2시간 후 체온 재측정", "항생제 투여 후 체온과 수술 부위 발적 추적 관찰"]),
        _ev(vs="fever", complaint=["열감 있고 소변 볼 때 불편하다고 함", "열감 조금 있다고 표현하고 오한은 없음"], urine=["cloudy"], lung=["clear"],
            judgement=["요로 감염 가능성"], tail=["소변 turbid하고 배뇨 시 불편감 있는 상태"],
            orders=["urine culture 시행 후 acetaminophen 650mg PO", "urine analysis, urine culture 시행 후 acetaminophen 1g IV"],
            med=["{t} acetaminophen 650mg PO", "{t} PRN acetaminophen 1g IV"], nursing=[["hydration"], ["hydration", "tepid"]],
            exam=["urine culture 검체 채취하여 검사실로 보냄"], plan=["배양 결과 확인 예정이며 2시간 후 체온 재측정", "수분 섭취 격려하며 배뇨 양상 관찰"]),
        _ev(vs="fever", complaint=["열감 없다고 하나 얼굴 붉어져 있음", "입이 마르고 기운 없다고 함"], lung=["clear"],
            judgement=["탈수 가능성", "수술 후 흡수열 가능성"], tail=["수술 부위와 호흡음 특이 소견 없고 경구 섭취 적은 상태"],
            orders=["수액 500cc 추가 주입, acetaminophen 650mg PO", "N/S 500cc 추가 후 체온 재측정"],
            med=["{t} N/S 500cc 연결하고 acetaminophen 650mg PO", "{t} N/S 500cc"], nursing=[["hydration", "tepid"], ["hydration"]], exam=[""],
            plan=["수액 주입 후 체온 재측정 예정이며 내일 아침 랩 F/U", "2시간 후 체온 재측정 예정"]),
    ],
    "통증": [_ev(vs="normal", vs_adj={"hr": (88, 104)}, nrs=(6, 8), complaint=["PCA 눌러도 통증 조절 안 된다고 함", "PCA 사용 중에도 수술 부위 통증 심해졌다고 호소함"],
               judgement=["PCA로 조절되지 않는 급성 통증"], tail=["NRS {nrs}점 통증 호소하며 PCA 사용에도 조절 안 되는 상태"],
               orders=["PRN 트라마돌 50mg IV 1회", "케토롤락 30mg IV 1회 투여 후 재사정", "PCA 농도 조절 및 PRN 트라마돌 50mg IV 1회"],
               med=["{t} PRN 트라마돌 50mg IV", "{t} 케토롤락 30mg IV", "{t} PRN 트라마돌 50mg IV"], nursing=[["position", "icepack"], ["position"]], exam=[""],
               plan=["30분 후 통증 재사정 예정이며 조절 안 되면 재노티", "통증 재사정 후 NRS 4점 이하 유지되는지 관찰"], pca=True),
           _ev(vs="normal", vs_adj={"hr": (88, 104)}, nrs=(6, 8), complaint=["수술 부위 통증 심해졌다고 호소함", "움직일 때 수술 부위 통증 심하다고 함"],
               judgement=["수술 부위 급성 통증"], tail=["수술 부위 NRS {nrs}점 통증 호소하는 상태"],
               orders=["PRN 트라마돌 50mg IV 1회", "케토롤락 30mg IV 1회 투여 후 재사정"],
               med=["{t} PRN 트라마돌 50mg IV", "{t} 케토롤락 30mg IV"], nursing=[["position", "icepack"], ["position"]], exam=[""],
               plan=["30분 후 통증 재사정 예정이며 조절 안 되면 재노티", "통증 재사정 후 NRS 4점 이하 유지되는지 관찰"])],
    "오심구토": [_ev(vs="normal", complaint=["오심 호소하며 구토 1회 있었음", "메스껍고 속 울렁거린다고 함"], judgement=["PCA 관련 오심 가능성", "마취 후 오심구토 가능성"],
                 tail=["오심 호소하며 구토 1회 있는 상태", "오심 호소하나 구토는 없는 상태"], orders=["온단세트론 4mg IV 1회", "메토클로프라미드 10mg IV, PCA 속도 조절"],
                 med=["{t} 온단세트론 4mg IV", "{t} 메토클로프라미드 10mg IV"], nursing=[["position"], ["position", "hydration"]], exam=[""],
                 plan=["항구토제 투여 후 오심 재사정, 지속 시 재노티", "오심 호전 후 식이 진행 예정"])],
    "출혈": [_ev(vs="normal", vs_adj={"hr": (92, 110), "sbp": (96, 118)}, complaint=["드레싱에 피 비친다고 호소함", "드레싱 젖은 느낌 있다고 함"], wound=["bleeding"],
               judgement=["수술 부위 출혈 가능성"], tail=["드레싱 혈액으로 젖어 있는 상태"], orders=["드레싱 교환 및 압박 드레싱, CBC F/U", "압박 드레싱 후 관찰, 트라넥삼산 500mg IV, CBC F/U"],
               med=["", "{t} 트라넥삼산 500mg IV"], nursing=[["compression"], ["compression", "position"]], exam=["CBC 채혈하여 검사실로 보냄", ""],
               plan=["CBC 결과 확인 후 주치의 노티 예정이며 드레싱 상태 1시간마다 관찰", "드레싱 상태 지속 관찰 예정"], recheck=True)],
    "저혈압": [_ev(vs="hypo", complaint=["어지럽다고 호소함", "일어설 때 어지럽고 식은땀 난다고 함"], mental=["alert", "drowsy"], urine=["decreased", "clear"],
                judgement=["체액 부족에 의한 저혈압 가능성", "PCA 관련 저혈압 가능성"], tail=["저혈압 상태"],
                orders=["N/S 500cc 로딩 후 V/S 재확인", "수액 로딩 및 PCA 일시 중단, 30분 후 재측정"], med=["{t} N/S 500cc 빠르게", "{t} N/S 500cc 빠르게"],
                nursing_by_order=[None, ["pca_hold"]],
                nursing=[["leg_up"], ["leg_up", "blanket"]], exam=[""], plan=["30분 후 혈압 재측정 예정이며 유지 안 되면 재노티", "수액 로딩 후 혈압 추적 관찰"])],
    "호흡곤란": [_ev(vs="normal", vs_adj={"rr": (24, 28), "spo2": (89, 93), "hr": (92, 108)}, complaint=["숨차다고 호소함", "가슴 답답하고 숨 쉬기 힘들다고 함"], lung=["crackle", "decreased", "sputum"],
                 judgement=["무기폐 가능성", "폐 합병증 가능성"], tail=["호흡 곤란 호소하는 상태"], orders=["O2 nasal 3L 적용, chest PA, ABGA", "산소 적용 후 SpO2 추적, chest PA 촬영"],
                 med=["", ""], nursing=[["o2", "breathing", "inspirometer", "position"]], exam=["병실에서 portable chest PA 촬영함"],   # a desaturating patient is not wheeled to radiology
                 plan=["chest PA 결과 확인 후 노티 예정이며 SpO2 지속 관찰", "산소 유지하며 1시간 간격 SpO2 확인 예정"], o2_after="O2 3L nasal")],
    "배액 이상": [_ev(vs="normal", vs_adj={"hr": (88, 104)}, complaint=["특이 호소 없음", "배액관 쪽 불편감 호소함"],
                  drain_text=["JP 배액 bloody하게 2시간 동안 150cc 증가함", "JP 배액 색 짙어지고 양 늘어 120cc 확인됨"],
                  judgement=["배액량 증가로 수술 부위 출혈 가능성"], tail=["배액 bloody하게 짙어지고 양 늘어난 상태"],
                  orders=["CBC F/U, 배액 양상 1시간마다 관찰", "배액관 milking 후 양상 관찰, CBC F/U"], med=["", ""], nursing=[["milking"]],
                  exam=["CBC 채혈하여 검사실로 보냄"], plan=["1시간 후 배액량 재확인 예정이며 증가 시 재노티"], recheck=True)],
    "섬망": [_ev(vs="normal", complaint=["밤새 소리 지르고 라인 빼려고 함", "장소와 시간 헷갈려 하며 집에 가겠다고 함"], mental=["confuse"],
               judgement=["수술 후 섬망 가능성"], tail=["지남력 저하되고 안절부절 못하는 상태"], orders=["쿠에티아핀 12.5mg PO 1회, 억제대 없이 보호자 상주", "할로페리돌 2.5mg IM 1회 후 관찰"],
               med=["{t} 쿠에티아핀 12.5mg PO", "{t} 할로페리돌 2.5mg IM"], nursing=[["reorient"]], exam=[""], plan=["야간 섬망 재발 관찰하며 낙상 예방 지속", "다음 근무에서 지남력 재사정 예정"])],
    "저혈당": [_ev(vs="normal", vs_adj={"hr": (90, 105)}, complaint=["BST 52mg/dL 확인되고 식은땀 난다고 함", "어지럽고 손 떨린다고 호소하여 BST 58mg/dL 확인함"], mental=["alert", "drowsy"],
                judgement=["금식 중 인슐린 투여에 의한 저혈당"], tail=["저혈당 상태"], orders=["50% DW 50cc IV 후 15분 뒤 BST 재측정", "주스 섭취 후 15분 뒤 BST 재측정"],
                med=["{t} 50% DW 50cc IV", "{t} 주스 150cc 섭취하도록 함"], nursing=[[]], exam=[""], plan=["15분 후 BST 재측정 예정이며 식사 시작 전까지 2시간마다 BST 측정 예정"], quick=True)],
    "고혈당": [_ev(vs="normal", complaint=["BST 320mg/dL 확인됨, 갈증 호소함", "식후 BST 410mg/dL 확인되고 특이 증상 없음"], judgement=["스트레스성 고혈당 가능성", "수술 후 고혈당"],
                tail=["고혈당 상태"], orders=["RI 6단위 SC 추가, 2시간 후 BST 재측정", "sliding scale 적용 및 BST 추적 관찰"], med=["{t} RI 6단위 SC", "{t} sliding scale에 따라 RI 4단위 SC"], nursing=[[]], exam=[""],
                plan=["2시간 후 BST 재측정 예정"])],
    "저칼슘혈증": [_ev(vs="normal", complaint=["손끝과 입 주위 저림 호소함", "양손 저리고 얼굴 주위 감각 이상하다고 함"], judgement=["갑상선 절제 후 저칼슘혈증 가능성"],
                  tail=["손끝과 입 주위 저림 호소하는 상태"], orders=["Ca 랩 응급 채혈, 칼슘 글루코네이트 1앰플 IV", "칼슘제 경구 추가 및 Ca 랩 F/U"],
                  med=["{t} 칼슘 글루코네이트 1앰플 IV 천천히 투여", "{t} 탄산칼슘 PO"], nursing=[[]], exam=["Ca, iPTH 응급 채혈하여 검사실로 보냄"],
                  plan=["Ca 결과 확인 후 노티 예정이며 저림 증상 관찰"])],
    "혈뇨": [_ev(vs="normal", complaint=["소변 붉다고 호소함", "소변백에 혈뇨 보이고 덩어리 섞여 있음"], urine=["hematuria"], judgement=["수술 부위 출혈에 의한 혈뇨 가능성"],
               tail=["혈뇨 보이는 상태"], orders=["방광 세척 속도 올리고 소변 색 관찰, CBC F/U", "수분 섭취 격려 및 소변 색 관찰"], med=["", ""], nursing=[["hydration"]],
               exam=["CBC 채혈하여 검사실로 보냄"], plan=["소변 색 1시간마다 관찰 예정이며 짙어지면 재노티"])],
}
# where the generic story does not fit the surgery
_NECK_BLEED = dict(complaint=["목이 붓고 답답하다고 호소함", "목 수술 부위 부어오르고 드레싱 젖어 있음"], wound=["bleeding"],
                   judgement=["경부 수술 부위 출혈과 혈종 가능성"], tail=["경부 부종과 드레싱 젖음 있어 호흡곤란·목소리 변화 관찰 중인 상태"],
                   orders=["즉시 병실 방문하여 확인, 침상 머리 올리고 산소 준비, CBC F/U"], med=[""], nursing=[["hob"]],
                   exam=["CBC 채혈하여 검사실로 보냄"], plan=["경부 부종과 호흡 양상, 목소리 변화 15분마다 관찰"], recheck=True)
_EVENT_OVERRIDES: dict[tuple[str, str], dict[str, Any]] = {
    ("Bilateral total thyroidectomy", "출혈"): _NECK_BLEED, ("MRND", "출혈"): _NECK_BLEED,
    ("ESS", "출혈"): dict(complaint=["코피 나서 거즈 자주 교환함", "목 뒤로 피 넘어간다고 함"], wound=["nose"], judgement=["비강 패킹 부위 출혈 가능성"], tail=["비강 출혈 지속되는 상태"],
                        orders=["비강 패킹 보강, 머리 올리고 냉찜질, 출혈 지속 시 재노티"], med=[""], nursing=[["icepack", "hob"]], exam=[""], plan=["코피 양 1시간마다 관찰 예정"], recheck=True),
    ("TURB", "출혈"): dict(complaint=["소변 붉어지고 덩어리 섞여 나옴"], wound=None, urine=["hematuria"], judgement=["방광 수술 부위 출혈 가능성"], tail=["혈뇨 짙어진 상태"],
                         orders=["방광 세척 속도 올리고 소변 색 관찰, CBC F/U"], med=[""], nursing=[["hydration"]], exam=["CBC 채혈하여 검사실로 보냄"],
                         plan=["소변 색 1시간마다 관찰 예정이며 짙어지면 재노티"], recheck=False),
    ("C-sec", "출혈"): dict(complaint=["패드 1시간에 한 장 적시는 질 출혈 있음"], wound=["clean"], judgement=["자궁 수축 부전에 의한 질 출혈 가능성"], tail=["질 출혈 양 늘어난 상태"],
                          orders=["자궁 저부 마사지 및 옥시토신 추가, CBC F/U"], med=["{t} 옥시토신 10단위 수액에 섞어"], nursing=[["fundal"]], exam=["CBC 채혈하여 검사실로 보냄"],
                          plan=["패드 양과 자궁 수축 1시간마다 확인 예정"], recheck=False),
    ("MRND", "배액 이상"): dict(drain_text=["JP 배액 우윳빛으로 변하고 양 늘어 150cc 확인됨"], judgement=["유미 누출 가능성"], tail=["배액 우윳빛으로 변한 상태"],
                              orders=["저지방 식이로 변경, 배액 양상 관찰, 외과 재확인", "금식 유지하고 배액 TG 검사 후 재노티"], med=["", ""], nursing=[["milking"]], exam=["배액 TG 검사 검체 검사실로 보냄"]),
}


def _derive_s3_2(form: dict[str, Any], patient: Patient, sc, rng: random.Random) -> None:
    """Event record: the event decides everything, and 발견→노티→투약→재측정 sit on one clock."""
    age = patient.age or 60
    drains = _scenario_drains(sc)
    if not (sc is not None and "s3_2.event" in sc.form):
        w = {"발열": 35, "통증": 25, "오심구토": 15, "출혈": 10, "저혈압": 5, "호흡곤란": 5}
        if drains:
            w["배액 이상"] = 5
        if age >= 70:
            w["섬망"] = 6
        if age >= 55:
            w["고혈당"], w["저혈당"] = 3, 2
        form["event"] = rng.choices(list(w), weights=list(w.values()))[0]
    ev = form["event"]
    no_wound = sc is not None and (sc.key in ("ESS", "TURB") or ("s3_1.dressing" in sc.form and sc.form["s3_1.dressing"] is None))
    cands = _EVENTS[ev]
    # PCA talk only for a patient who has a PCA (2026-10-18: "PCA 관련 오심" for a patient on 정규 진통제)
    pca_ok = sc is not None and any("pca" in a for a in (sc.form.get("attachments") or []))   # the surgery leaves a PCA at all
    if not pca_ok and form.get("pain_med") == "pca":
        form["pain_med"] = "regular"
    if not pca_ok:
        cands = [c for c in cands if not c.get("pca")] or cands
    if no_wound and (sc.key, ev) not in _EVENT_OVERRIDES:
        cands = [c for c in cands if not c.get("wound")] or cands      # no wound-infection or bleeding story without a wound
    var = dict(rng.choice(cands))
    var.update(_EVENT_OVERRIDES.get((sc.key if sc else "", ev), {}))
    t0 = rng.choice([6, 7, 9, 10, 11, 13, 14, 15, 16, 18, 19, 20, 21, 22, 23, 1, 3, 5]) * 60 + rng.choice([0, 0, 10, 20, 30, 40, 50])
    if ev == "섬망" and 7 * 60 <= t0 < 20 * 60:
        var["complaint"] = [c for c in var["complaint"] if "밤" not in c] or var["complaint"]   # "밤새 소리 지르고" found at noon
    quick = bool(var.get("quick"))
    t_noti = t0 + (rng.randint(3, 6) if quick else rng.randint(5, 15))
    t_med = t_noti + (rng.randint(2, 5) if quick else rng.randint(10, 30))
    # recheck after the drug has had time to work (2026-10-18: juice at 19:33, recheck at 19:27; 38.1 → 36.6 23 min after PO)
    form["found_time"], form["noti_time"] = _clock(t0), _clock(t_noti)   # re_time follows the drug (below)
    v = random_vitals(rng, var.get("vs", "normal"), with_spo2=True)
    v["spo2"] = v["spo2"] or rng.randint(95, 99)
    v["o2"] = "room air"
    for k, (lo, hi) in var.get("vs_adj", {}).items():
        v[k] = rng.randint(lo, hi)
    v["dbp"] = min(v["dbp"], v["sbp"] - 30)
    form["vitals"] = v
    form["nrs"] = rng.randint(*var.get("nrs", (1, 3)))
    if ev == "통증":
        form.pop("pain_med", None)        # the complaint and judgement already say how pain is being treated
    form["complaint"] = rng.choice(var["complaint"])
    if sc is not None and sc.key == "Tracheostomy" and re.search(r"[다라]고 (하|함|표현|호소)", form["complaint"]):
        form["complaint"] = "필담으로 " + form["complaint"]   # a cuffed tracheostomy writes it down (2026-10-18 2차 검수)
    form["mental"] = rng.choice(var.get("mental", ["alert"]))
    for k, default in (("lung", None), ("wound", None if no_wound else ["clean"]), ("abdomen", ["soft", "normal"]), ("urine", ["clear"])):
        opts = var.get(k, default)
        if opts is None or k not in form:
            form.pop(k, None)
            continue
        form[k] = rng.choice(opts)
    foley_keep = sc is not None and "keep" in (sc.form.get("foley") or []) and (patient.pod or 0) <= 1
    if "urine" not in var and foley_keep and rng.random() < 0.6:
        form["urine"] = "foley"
    form["iv_site"] = "phlebitis" if rng.random() < 0.05 else "clean"
    form["leg"] = rng.random() < 0.95
    form["judgement"] = rng.choice(var["judgement"])
    head = f"BT {v['bt']}, BP {v['sbp']}/{v['dbp']}, HR {v['hr']}" + (f", RR {v['rr']}, SpO2 {v['spo2']}%" if ev == "호흡곤란" else "")
    form["noti_content"] = f"{head}, {rng.choice(var['tail']).format(nrs=form['nrs'])}"
    idx = [j for j, o in enumerate(var["orders"]) if pca_ok or "PCA" not in o] or list(range(len(var["orders"])))
    i = rng.choice(idx)
    form["orders"] = var["orders"][i]
    if not pca_ok and "PCA" in form["judgement"]:
        form["judgement"] = next((j for j in var["judgement"] if "PCA" not in j), form["judgement"].replace("PCA 관련 ", ""))
    if "PCA" in form["orders"] + form["judgement"] and ev != "통증":   # the pain event says its PCA in the complaint
        form["pain_med"] = "pca"
    if ev == "오심구토" and (patient.pod or 1) >= 2 and "마취 후" in form["judgement"]:
        form["judgement"] = "PCA 관련 오심 가능성" if form.get("pain_med") == "pca" else "장운동 저하 관련 오심 가능성"   # PONV is the first day
    if ev == "오심구토":
        form["noti_content"] = f"{head}, {'오심 호소하며 구토 1회 있는 상태' if '구토' in form['complaint'] else '오심 호소하나 구토는 없는 상태'}"
    if ev == "발열" and form.get("pain_med") in ("prn_po", "prn_iv"):
        form["pain_med"] = "regular"     # "PRN 아세트아미노펜 드셨습니다" then acetaminophen again
    if ev == "저혈당" and form.get("mental") == "drowsy" and "주스" in form["orders"]:
        i, form["orders"] = 0, var["orders"][0]          # a drowsy patient gets IV dextrose, not juice by mouth
    if ev != "통증" and form.get("pain_med") == "prn_iv" and int(form.get("nrs") or 0) < 4:
        form["pain_med"] = "regular"                     # "아파하셔서 PRN" at NRS 2
    meds = var.get("med") or [""]
    med = meds[i] if len(meds) == len(var["orders"]) else rng.choice(meds)   # the drug given is the drug ordered
    oral = "PO" in med or "섭취" in med
    t_re = t_med + (rng.randint(15, 20) if quick else rng.randint(60, 90) if oral else rng.randint(30, 60))
    form["re_time"] = _clock(t_re)
    if med:
        form["med_given"] = med.format(t=_clock(t_med))
    else:
        form.pop("med_given", None)
    nursing = list(rng.choice(var.get("nursing") or [[]]))
    by_order = (var.get("nursing_by_order") or [None] * len(var["orders"]))[i] if var.get("nursing_by_order") else None
    if by_order:
        nursing += by_order
    if "PCA 속도 조절" in form["orders"]:
        nursing.append("pca_down")       # the ordered PCA change is charted
    if "방광 세척 속도" in form["orders"]:
        nursing.append("cbi_up")
    anal = sc is not None and sc.key in ("Hemorrhoidectomy", "Rectal prolapse OP")
    limb_or_breast = patient.department in ("정형외과", "유방외과") or "유방" in patient.diagnosis or (sc is not None and sc.key == "ESS")
    if "icepack" in nursing and anal:
        nursing = ["sitz" if x == "icepack" else x for x in nursing]   # an anal wound gets 좌욕
    elif "icepack" in nursing and not limb_or_breast:
        nursing = [x for x in nursing if x != "icepack"]
    night = t0 % 1440 >= 22 * 60 or t0 % 1440 < 6 * 60
    if night:
        nursing = [x for x in nursing if x != "ambulation"]   # 2026-10-18: 새벽 1시 20분 "보호자 동반 병동 복도 보행"
    if nursing:
        form["nursing"] = nursing
    else:
        form.pop("nursing", None)
    exams = var.get("exam") or [""]
    exam = next((x for x in exams if "chest PA" in x), "") if "chest PA" in form["orders"] else \
        next((x for x in exams if "CBC" in x), "") if "CBC" in form["orders"] else rng.choice(exams)   # the ordered test is done
    if night and "도보로" in exam:
        exam = "병실에서 portable chest PA 촬영함"   # nobody walks a febrile patient to radiology at 1 a.m.
    if exam:
        form["exam"] = exam
    else:
        form.pop("exam", None)
    if ev == "배액 이상":
        form["drain"] = rng.choice(var["drain_text"])
    else:
        d = _drain_text(rng, patient, sc, "s3_2") if (patient.pod or 0) <= 3 else ""
        if d:
            form["drain"] = d
        else:
            form.pop("drain", None)
    resp = rng.choices(["improved", "same", "worse"], weights=[70, 25, 5])[0]
    form["response"] = resp
    # the recheck starts from the finding (2026-10-18: BT 38.7 → 36.2 within 40 min; "악화" while BT fell)
    rv = dict(v)
    if ev != "저혈압":   # a recheck never reads the same pressure to the digit (2026-10-18: 133/72 → 133/72 in 9 of 12)
        rv["sbp"], rv["dbp"] = int(v["sbp"]) + rng.choice([-8, -6, -4, -2, 2, 4, 6]), int(v["dbp"]) + rng.randint(-5, 4)
        rv["rr"] = int(v["rr"]) + rng.randint(-2, 1)
    if resp == "improved":
        rv["bt"] = round(max(36.8, float(v["bt"]) - rng.uniform(0.5, 1.2)), 1) if ev == "발열" else round(float(v["bt"]) + rng.uniform(-0.2, 0.1), 1)
        rv["hr"] = max(70, int(v["hr"]) - rng.randint(5, 15)) if int(v["hr"]) > 90 else int(v["hr"]) + rng.randint(-4, 4)
        if ev == "저혈압":
            rv["sbp"], rv["dbp"] = int(v["sbp"]) + rng.randint(12, 25), int(v["dbp"]) + rng.randint(6, 12)
        if ev == "호흡곤란":
            rv["rr"] = int(v["rr"]) - rng.randint(4, 7)
    elif resp == "worse":
        rv["bt"] = round(float(v["bt"]) + (rng.uniform(0.2, 0.5) if ev == "발열" else 0.0), 1)
        rv["hr"] = int(v["hr"]) + rng.randint(5, 15)
        if ev == "저혈압":
            rv["sbp"] = int(v["sbp"]) - rng.randint(4, 10)
    else:
        for k in ("sbp", "dbp", "hr", "rr"):
            rv[k] = int(v[k]) + (rng.choice([-4, -3, -2, -1, 1, 2, 3, 4]) if k == "sbp" else rng.randint(-4, 4))   # never the same pressure
        rv["bt"] = round(float(v["bt"]) - (rng.uniform(0, 0.3) if ev == "발열" else rng.uniform(-0.1, 0.1)), 1)
    rv["dbp"] = min(int(rv["dbp"]), int(rv["sbp"]) - 30)
    rv["spo2"] = rv["spo2"] or rng.randint(95, 99)
    rv["o2"] = var.get("o2_after", "room air")
    if var.get("o2_after"):
        rv["spo2"] = rng.randint(95, 98)
    if resp == "worse" and ev == "호흡곤란":
        rv["spo2"] = rng.randint(90, 93)
    form["re_vitals"] = rv
    if var.get("recheck") and resp == "improved":   # "아직 큰 변화 없고" + "더 이상 변화 없구요" read as two answers (2026-10-18)
        form["recheck"] = "nose" if sc is not None and sc.key == "ESS" else "no_change" if form.get("drain") else "dressing"
    else:
        form["recheck"] = "na"
    form["plan"] = rng.choice(var["plan"])
    if resp == "improved" and len(var["plan"]) > 1:   # after an improvement the plan is not "투여 후 재사정 / 30분 후 재측정" again
        later = [x for x in var["plan"] if not re.search(r"투여 후|30분 후|15분 후", x)]
        if later:
            form["plan"] = rng.choice(later)
    if resp == "worse":                   # the re-notify is in the response line; the plan is not "지속 시 재노티" again
        form["plan"] = rng.choice(["추가 처방 시행 후 30분 뒤 재평가", "주치의 직접 확인 예정이며 30분 간격으로 활력징후 측정"])
        form["worse_order"] = {"발열": "blood culture와 항생제 추가", "통증": "PRN 진통제 추가", "오심구토": "다른 항구토제 추가",
                               "출혈": "주치의 직접 확인과 CBC 재검", "저혈압": "N/S 500cc 추가 로딩", "호흡곤란": "O2 5L mask로 변경, ABGA",
                               "배액 이상": "주치의 직접 확인", "섬망": "추가 진정제", "저칼슘혈증": "칼슘 추가 투여", "혈뇨": "방광 세척 속도 증가"}.get(ev, "추가 처치")
    # what the re-assessment actually measured (2026-10-18: no NRS after the analgesic, no BST number in a glucose event)
    if ev == "통증":
        form["re_nrs"] = max(1, int(form["nrs"]) - rng.randint(3, 5)) if resp == "improved" else int(form["nrs"]) - rng.randint(0, 1)
        if resp == "improved" and "30분 후 통증 재사정" in form["plan"]:
            form["plan"] = "NRS 4점 이하 유지되는지 관찰하고 조절 안 되면 재노티"
    else:
        form.pop("re_nrs", None)
    if ev in ("저혈당", "고혈당"):   # the BST number is the outcome: corrected, so improved, with the follow-up (not "15분 후 재측정" again)
        form["response"] = "improved" if ev == "저혈당" else "na"   # 고혈당 "특이 증상 없음" has nothing to feel better about
        form["plan"] = "식사 시작 전까지 2시간마다 BST 측정" if ev == "저혈당" else "식전 BST 추적 관찰하며 sliding scale 적용"
        start = int(re.search(r"BST (\d+)", form["complaint"]).group(1)) if re.search(r"BST (\d+)", form["complaint"]) else (55 if ev == "저혈당" else 320)
        form["re_bst"] = rng.randint(95, 140) if ev == "저혈당" else max(160, start - rng.randint(60, 140))
        form["noti_content"] = form["noti_content"].replace(f"BT {v['bt']}", f"BST {start}mg/dL, BT {v['bt']}", 1)
    else:
        form.pop("re_bst", None)
    if resp == "improved" and ev in ("배액 이상", "출혈", "혈뇨"):
        form["response"] = "na"           # "환자 편해졌다고 하십니다" after "특이 호소 없음"; the recheck line says what changed
    if resp == "improved" and ev == "섬망":
        form["response"] = "settled"
    if "소변" in form["complaint"]:
        form.pop("urine", None)           # TURB 출혈: the complaint already describes the urine
    if sc is not None and sc.key == "BKA":
        form.pop("leg", None)             # "양측 하지 부종" for an amputee
    elif "leg" in form:
        form["leg"] = True                # a new leg swelling would be its own SBAR, not "관찰 중"


def _derive_s4(form: dict[str, Any], patient: Patient, sc, rng: random.Random) -> None:
    """Discharge education: home drugs by age, ER criteria by admission kind, outpatient date in the patient's calendar."""
    age = patient.age or 50
    chemo = patient.kind == "chemo"
    form["report_edu"] = "chemo" if chemo else ("nowound" if sc is not None and sc.key in ("ESS", "TURB") else "op")
    form["id_check"] = True                    # 퇴원 범주 1번 (user 2026-10-17); 5% 빠진 기록이 있었음 (2026-10-18 2차 검수)
    if chemo and ("FOLF" in (patient.regimen or "") or form.get("device") == "picc"):
        form["id_check"] = False              # the port needle / PICC is its own sentence, not "정맥주사 제거 부위"
    first_day = patient.day or 1
    pump = chemo and "FOLF" in (patient.regimen or "")
    if chemo:   # the discharge is the morning after the infusion (2026-10-18: "항암 중 오심 … 호전" dictated before the drug ran on D1)
        patient.day = 3 if pump else first_day + 1            # 5-FU pump (46 h from D1) comes off on D3; the rest go home the next morning
        if pump and not form.get("device_note"):
            form["device_note"] = "5-FU 펌프 제거하고 케모포트 바늘 제거 부위 지혈된 것 확인하였습니다"
    if age < 50:
        form["home_meds"] = "none" if rng.random() < 0.85 else "continue"
    else:
        form["home_meds"] = rng.choices(["continue", "none", "continue_aspirin_later", "changed"], weights=[50, 30, 0 if chemo else 10, 10])[0]
    form["teachback"] = rng.choices(["both", "patient", "caregiver", "re_edu"], weights=[70, 20, 5 if age >= 80 else 0, 5])[0]
    if "보호자 내원 후" in str(form.get("discharge_date") or ""):
        form["teachback"] = "patient"      # the guardian arrives at 15:00, after this 09:00 teaching
    if "없음" in str(form.get("discharge_meds") or ""):
        form["side_effect_edu"] = False   # 복약지도문 without a prescription (2026-10-17)
    m = re.match(r"(\d+)월 (\d+)일", patient.op_date or "")
    if m:
        md = (int(m.group(1)), int(m.group(2)))
        now = datetime.now()                                  # the same year record_datetime will give this discharge
        stay = (patient.day - 1) if chemo else (patient.pod or 0)
        year = now.year if datetime(now.year, *md) + timedelta(days=stay) <= now else now.year - 1
        op = datetime(year, *md)
        offset = rng.randint(12, 21)
        if not chemo and patient.pod:
            offset = max(offset, patient.pod + rng.randint(5, 9))   # a 21-day BKA stay still has its clinic after discharge
        same_day_admit = "입원 수속" in str(form.get("opd_exam") or "")
        if chemo:   # D1 = op_date; the clinic is the day before the next infusion (weekly K+TC: D8, D15), or that day when admitted from it
            cycle = int(sc.form.get("_cycle_days") or (14 if pump else 21)) if sc is not None else (14 if pump else 21)
            days = sorted(sc.form.get("_days") or [1]) if sc is not None and not pump else [1]   # FOLF [1, 2] are pump days, not infusions
            later = [d for d in days if d > first_day]
            next_rel = later[0] if later else cycle + 1
            offset = next_rel - (1 if same_day_admit else 2)
        visit = op + timedelta(days=offset)
        while visit.weekday() >= 5:                           # no clinic on a weekend (2026-10-18: 28% Sat/Sun)
            visit += timedelta(days=1)
        clock = ['오전 9시', '오전 10시 30분', '오전 11시', '오후 2시', '오후 3시']
        if "8시 30분 채혈" in str(form.get("opd_exam") or ""):
            clock = clock[1:3]                # the 08:30 blood is for a morning visit (2026-10-18: 공복 채혈 후 오후 3시 진료)
        form["opd"] = f"{visit.month}월 {visit.day}일 {rng.choice(clock)}"
        if chemo:                                            # 다음 입원 일자: the cycle after the clinic check (user 2026-10-17)
            nxt = visit if same_day_admit else visit + timedelta(days=1)
            while nxt.weekday() >= 5:
                nxt += timedelta(days=1)
            form["next_admission"] = f"{nxt.month}월 {nxt.day}일"
            if form.get("further") == "next_cycle":
                form.pop("further")                           # "다음 차수 입원 예정" is now the 다음 입원 일자 sentence
    if not chemo:
        form.pop("next_admission", None)
    if any(w in form.get("driving", "") for w in ("무거운", "활동 제한")):
        form.pop("activity", None)
    abdominal = not chemo and sc is not None and sc.form.get("abdomen", 1) is not None
    cancer = any(w in patient.diagnosis for w in ("암", "종양", "전이"))
    if "CT" in form.get("opd_exam", "") and not (abdominal and cancer):   # a breast or knee patient has no CT before the clinic
        form["opd_exam"] = rng.choice(["따로 영상검사나 혈액검사 없음", "외래 당일 8시 30분 채혈 후 진료 볼 것"] if not chemo else ["다음 항암 전 채혈할 것"])
    ex = form.get("opd_exam", "")                             # 검사 전 주의할 점 follows the test itself
    if "CT" in ex:
        form["exam_prep"] = rng.choice(["CT 검사 4시간 전부터 금식하고 조영제 알레르기 있으면 미리 말하도록", "검사 4시간 전부터 금식하도록"])
    elif "채혈" in ex:
        form["exam_prep"] = rng.choice(["채혈은 아침 공복으로 오도록", "채혈 있어 외래 당일 아침은 금식하고 오도록"])
    else:
        form.pop("exam_prep", None)
    if form.get("device") == "stoma" or (sc is not None and sc.key in ("LAR", "Ileostomy repair")):
        form["referral"] = [r for r in form.get("referral", []) if r != "stoma"]   # the stoma line says it; a closed stoma has no 장루 외래
    if sc is not None and "referral" not in sc.form:
        cancer = any(w in patient.diagnosis for w in ("암", "종양", "전이"))
        form["referral"] = ["nutrition"] if cancer and rng.random() < 0.15 else []
    if sc is not None and "activity" not in sc.form and not chemo and "activity" in form:
        form["activity"] = "full" if sc.los[1] <= 3 else "walk_no_heavy"   # 보행기 체중 부하 is for leg surgery only
    # a leaflet sentence replaces the generic sentence of its category (user 2026-10-17: 범주당 한 번, 상처 교육 두 번 금지)
    if form.get("wound_note"):
        form.pop("wound", None)
    if form.get("diet_note"):
        form.pop("diet_edu", None)
        form["dumping"] = False
    if form.get("activity_note"):
        form.pop("activity", None)
        if any(w in form["activity_note"] for w in ("운전", "복직")) or ("무거운" in form["activity_note"] and "무거운" in str(form.get("driving") or "")):
            form.pop("driving", None)         # 2026-10-18: "무거운 것 들기는 4주간 피하고…" + "1개월간 무거운 물건 피하고…"
    if form.get("device_note"):
        form.pop("device", None)
    if re.search(r"38도|발열|고열|열 나|열,|열 지속", form.get("report_note", "")):
        form.pop("report_edu", None)                          # the leaflet warning already lists the fever criterion
    if re.search(r"조직검사|항암 여부|방사선|병리", form.get("opd_note", "")):
        form.pop("further", None)
    if age >= 70 and "복직" in str(form.get("driving") or ""):
        form["driving"] = "운전은 외래에서 확인 후 가능함"   # nobody tells a 78-year-old when to go back to work ("가능함을 설명")
    if age >= 80 and "운전" in str(form.get("driving") or ""):
        form.pop("driving", None)
    if sc is not None and sc.key == "Hemorrhoidectomy" and form.get("wound") == "dressing":
        form.pop("wound")
        form["wound_note"] = form.get("wound_note") or "배변 후 미지근한 물로 좌욕하고 항문 부위 청결하게 유지하도록 교육하였습니다"
    if sc is not None and sc.key == "BKA" and "외상" in patient.diagnosis and form.get("diet_edu") == "dm":
        form["diet_edu"] = "gd"
    if form.get("activity") == "weight_bearing" and age < 60:
        form["activity"] = "crutch"           # a young ORIF patient uses crutches, not a walker
    notes = " ".join(str(form.get(k) or "") for k in ("wound_note", "precautions", "activity_note", "device_note", "opd_note", "diet_note"))
    if "좌욕" in notes and form.get("wound") == "glue":
        form.pop("wound")                     # perineal wound: 좌욕, not "피부 접착제"
    if form.get("activity") == "full" and re.search(r"쪼그려|계단|무거운|달리기|뛰|운동은", notes):
        form.pop("activity")                  # "활동 제한 없다" next to "쪼그려 앉기·계단 피하도록"
    if "사람 많은" in notes and "사람 많은" in str(form.get("driving") or ""):
        form.pop("driving", None)
    if form.get("opd") and any("8시 30분 채혈" in str(v) for v in form.values() if isinstance(v, str)):
        form["opd"] = re.sub(r"오전 9시|오후 \d+시( \d+분)?", "오전 10시 30분", form["opd"])   # the 08:30 blood (exam or leaflet) is for a late-morning visit
    if _upper_limb(patient.diagnosis) and re.search(r"항응고|리바록사반|에독사반|에녹사파린", str(form.get("discharge_meds") or "")):
        plain = [x for x in _pool(sc, "discharge_meds", "s4") if not re.search(r"항응고|리바록사반|에독사반|에녹사파린", x)]
        form["discharge_meds"] = rng.choice(plain) if plain else "진통제 1주분, 근이완제, 위장약"   # no VTE prophylaxis after arm surgery (2026-10-18: 쇄골 골절 + 리바록사반)
    if _upper_limb(patient.diagnosis) and form.get("activity") in ("walk_no_heavy", "weight_bearing", "crutch"):
        form["activity"] = "arm_rest"         # shoulder/wrist: the arm rests, the legs walk
    if "갑상선" in patient.diagnosis and form.get("further") in ("pending_path", "chemo"):
        form["further"] = "rai"               # 2026-10-18: 갑상선암 MRND "보조 항암 여부"


def _diet_for_day(sc, pod: int, rng: random.Random) -> str:
    """Diet stage of an abdominal-surgery patient on this POD: npo → sow → ld → sd → gd (minor surgery climbs in a day)."""
    minor = sc.los[1] <= 3
    stage = (("sow", "ld") if pod == 0 else ("sd", "gd")) if minor else \
        {0: ("npo",), 1: ("npo", "sow"), 2: ("sow", "ld"), 3: ("ld", "sd")}.get(pod, ("sd", "gd"))
    allowed = [x for x in (sc.form.get("s5.diet") or sc.form.get("diet") or []) if x in stage]
    return rng.choice(allowed) if allowed else stage[-1]


def _derive_s5(form: dict[str, Any], patient: Patient, sc, rng: random.Random) -> None:
    """Handover: one patient's day. History by age, fever numbers match the summary, gas-out matches the diet,
    I/O lists the drain that exists, lines carry the patient's own dates, plans fit the day of stay."""
    age = patient.age or 50
    chemo = patient.kind == "chemo"
    pod = patient.pod or 0
    lo, hi = sc.los if sc else (2, 5)
    p_none = 0.92 if age < 40 else 0.5 if age < 60 else 0.25
    if rng.random() < p_none:
        form["history"] = ["none"]
    else:
        w = {k: v for k, v in _HISTORY_W.items() if k in ("htn", "dm", "heart", "stroke", "lung", "ckd") and (age >= 60 or k in ("htn", "dm"))}
        form["history"] = _weighted_distinct(rng, w, 1 if age < 60 else rng.choice([1, 1, 2]))
    dm = "dm" in form["history"]
    if rng.random() < 0.8:
        form.pop("allergy", None)
        form["allergy_none"] = True
    else:
        form["allergy"] = rng.choice(["조영제", "페니실린", "NSAIDs", "새우", "복숭아"])
        form["allergy_none"] = False
    form["isolation"] = "contact" if rng.random() < 0.05 else "none"
    form["code"] = "dnr" if age >= 80 and rng.random() < 0.1 else "none"
    allowed_cg = list(sc.form.get("caregiver") or []) if sc is not None else []   # 2026-10-18 검수: 시나리오 보호자를 덮어썼음
    if age < 20:
        form["caregiver"] = "parent"                                           # 17세에 "배우자분 상주"
    elif allowed_cg:
        form["caregiver"] = rng.choice(allowed_cg)
    else:
        form["caregiver"] = rng.choices(["spouse", "child", "caregiver", "none", "intermittent"],
                                        weights=[40, 15 if age >= 45 else 0, 5, 30, 10] if age < 65 else [30, 30, 15, 10, 15])[0]   # no grown child at 30
    form["consciousness"] = "drowsy" if pod == 0 and not chemo and rng.random() < 0.1 else "alert"
    vs = rng.choices(["stable", "fever_resolved", "fever", "hypotension", "tachy"], weights=[75, 10, 5, 2, 8] if chemo else [60, 20, 5, 5, 10])[0]
    form["vs_summary"] = vs
    form["bt_peak"] = round(rng.uniform(38.0, 39.0), 1)          # "37.8까지 올라서 해열제" is below the antipyretic line
    form["bt_now"] = round(rng.uniform(38.0, 38.9), 1) if vs == "fever" else round(rng.uniform(36.4, 37.4), 1)
    form["sbp"], form["dbp"], form["hr"] = rng.randint(82, 98), rng.randint(45, 60), rng.randint(102, 115)   # 120+ would be notified, not "좀 빠르고"
    nrs = rng.choice([0, 0, 1, 2]) if chemo else rng.randint(*{0: (3, 6), 1: (2, 5)}.get(pod, (1, 4)))
    if not chemo and "pain_mgmt" in form:
        if pod >= 4 and form["pain_mgmt"] in ("pca", "pca_prn"):
            form["pain_mgmt"] = "po"                    # the PCA is long gone by POD 4
        elif pod == 0 and hi >= 4 and form["pain_mgmt"] in ("po", "none"):
            form["pain_mgmt"] = rng.choice(["pca", "pca_prn"])
    pm = form.get("pain_mgmt")
    form["nrs"] = min(nrs, 2) if pm == "none" else max(nrs, 2) if pm in ("pca", "pca_prn") else nrs
    abdominal = not chemo and sc is not None and sc.form.get("abdomen", 1) is not None
    if abdominal and "diet" in form:      # the diet climbs with the day after surgery
        form["diet"] = _diet_for_day(sc, pod, rng)
    elif "diet" in form:                  # chemo, breast, thyroid, joints: they eat; diabetics get the diabetic diet
        form["diet"] = "dm" if "dm" in form["history"] else "gd"
    if form.get("consciousness") == "drowsy" and "diet" in form:
        form["diet"] = "npo"              # 2026-10-18 2차 검수: "기면 상태로 부르면 눈 뜨심" + "SOW 시작했고 잘 드셨어요"
    d = form.get("diet")
    if "gas_out" in form:
        if d == "npo":
            form["gas_out"] = False
        elif d == "sow":
            form["gas_out"] = True        # "가스 아웃 확인되어 물 시작"
        else:
            form.pop("gas_out")       # already past water: nobody announces gas
    # The shift that hears the handover decides what can be said (2026-10-18 검수: POD 0 at 07:00 is before surgery,
    # chemo "주입 중" at 07:00, "오전 외래 CT 이송 준비" handed to the evening, "퇴원 교육" handed to the night).
    if form.get("gas_out"):
        shift = 23                    # "금일 가스 아웃 … 저녁부터 물 시작"
    elif chemo or pod == 0:
        shift = rng.choice([15, 23, 23])
    else:
        shift = rng.choice([7, 15, 23])
    form["_shift"] = shift
    if shift != 7:
        form.pop("sleep", None)       # "밤에 잘 주무셨습니다" belongs to the 07:00 handover
    ready = pm not in ("pca", "pca_prn") and d not in ("npo", "sow", "ld") and vs not in ("fever", "hypotension", "tachy")
    near_dc = (chemo and vs != "fever") or (pod >= lo - 1 and ready)   # PCA, 미음, 발열 환자에게 퇴원 처방/교육 없음
    had_foley = sc is not None and "keep" in (sc.form.get("foley") or [])
    if not chemo and pod == 0 and had_foley:
        form["voiding"] = "foley"
    elif form.get("voiding") == "foley_removed" and (pod == 0 or pod > 2 or not had_foley):
        form["voiding"] = "self"          # "소변줄 어제 제거" only on POD 1-2 of a surgery that had one
    if pod <= 1 and not chemo:
        form["bowel"] = "diarrhea" if rng.random() < 0.05 else "none_yet"
    else:
        form["bowel"] = rng.choices(["done", "none_yet", "diarrhea"], weights=[7, 2, 1] if chemo else [6, 3, 1])[0]
    if shift == 7:
        form["sleep"] = rng.choices(["good", "poor", "hypnotic"], weights=[70, 20 if form["nrs"] >= 3 else 0, 10 if age >= 65 else 3])[0]   # "통증으로 수면 불량" needs pain
    drain = _drain_text(rng, patient, sc, "s5") if pod <= 4 or rng.random() < 0.5 else ""
    if drain:
        form["drain"] = drain
    else:
        form.pop("drain", None)
    if vs == "hypotension":
        form["fluid"] = "N/S 500cc 로딩 후 하트만 100cc/hr"     # "수액 로딩 중" with 5DW 40cc/hr
    hours = 24 if shift == 7 else 8                               # 07:00 reports the day's total, 15/23 the shift's
    m = re.search(r"(\d+)\s*cc/hr", str(form.get("fluid") or ""))
    iv = int(round(int(m.group(1) if m else 80) * hours * rng.uniform(0.85, 1.0) / 50) * 50)   # never more than the pump rate
    io = f"수액 {iv}, 소변 {rng.randrange(1200, 2400, 100) if hours == 24 else rng.randrange(400, 900, 50)}"
    if ("JP" in drain or "Hemovac" in drain) and "제거" not in drain:
        amounts = [int(x) for x in re.findall(r"(\d+)\s*cc", drain)]
        amount = (amounts[0] * 2 if "각" in drain and len(amounts) == 1 else sum(amounts)) if amounts else rng.randrange(20, 120, 10)   # "각 40cc, 30cc" = 70
        io += f", {'Hemovac' if 'Hemovac' in drain else 'JP'} {amount}"   # same number(s) as the drain line
    if chemo or d in ("sd", "gd", "soft", "dm"):
        io = f"경구 {rng.randrange(800, 1800, 100) if hours == 24 else rng.randrange(300, 700, 50)} " + io
    elif d in ("sow", "ld"):
        io = f"경구 {rng.randrange(200, 600, 50) if hours == 24 else rng.randrange(100, 300, 50)} " + io
    form["io"] = io
    if chemo or pod >= 5 or (pod >= 3 and rng.random() < 0.7) or "없음" in form.get("antibiotic", ""):
        form.pop("antibiotic", None)
    elif "antibiotic" in form and "메트로니다졸" in form["antibiotic"] and not (sc is not None and sc.key in ("LAR", "Lapa RHC", "Ileostomy repair", "Rectal prolapse OP")):
        form["antibiotic"] = "세파졸린 q8h"   # 메트로니다졸 is for bowel surgery (2026-10-18: 탈장·자궁·신장에도 나옴)
    elif "antibiotic" in form and "메트로니다졸" in form["antibiotic"]:
        form["antibiotic"] = "세프트리악손 q24h, 메트로니다졸 q8h"   # "추가" with nothing to add to
    if chemo:
        prn = ["항구토제 1회"] if rng.random() < 0.4 else []
    elif pod <= 1:
        prn = rng.choice([["트라마돌 1회"], ["항구토제 1회"], ["트라마돌 1회, 항구토제 1회"], []])
    else:
        prn = ["트라마돌 1회"] if rng.random() < 0.3 else []
    if prn and form.get("pain_mgmt") == "pca_prn":
        rest = [x.strip() for x in prn[0].split(",") if "트라마돌" not in x]
        prn = [", ".join(rest)] if rest else []
    if prn:
        form["prn"] = prn[0]
    else:
        form.pop("prn", None)
    form["o2"] = rng.choice(["nasal", "weaning"]) if pod == 0 and not chemo and rng.random() < 0.4 else "none"
    if sc is not None and sc.key == "Tracheostomy":
        form["o2"] = "none"           # not "O2 nasal" through a tracheostomy
    if not chemo and hi >= 7 and pod <= 2 and rng.random() < 0.2:
        form["transfusion"] = "PRBC 1 pack 수혈 완료"
    else:
        form.pop("transfusion", None)
    sp = [x for x in _pool(sc, "special", "s5") if ("퇴원" not in x or near_dc) and _fits_shift(x, shift, "special")]
    if chemo:   # 15:00 = the bag is running, 23:00 = done; the 5-FU pump keeps going either way
        sp = [x for x in sp if "펌프" in x or ("주입 중" not in x if shift == 23 else "주입 완료" not in x)] or sp
        if "펌프" in str(form.get("line") or ""):
            sp = [x for x in sp if "펌프 연결" not in x] or sp   # the line already says the pump is connected
    if pod > 2:
        sp = [x for x in sp if not re.search(r"소변줄[^,.]*제거 후", x)]   # POD 4 "소변줄 제거 후 자가배뇨 확인" is old news
    if form.get("voiding") == "foley":   # "Foley 유지 중입니다" + "소변줄 유지 중, 소변 맑음" (2026-10-18)
        sp = [x for x in sp if not re.search(r"소변줄[^,.]*(제거 (후|함)|유지)|자가배뇨", x)]
    elif form.get("voiding") in ("self", "foley_removed", "retention"):
        sp = [x for x in sp if not re.search(r"소변줄[^,.]*(제거 예정|유지)", x)]   # "소변줄 내일 아침 제거 예정" + "소변 잘 보세요"
    if d == "npo" or form.get("gas_out") is False:
        sp = [x for x in sp if "가스 배출" not in x]   # "gas out 아직" + "회장루 가스 배출 확인되고" (2026-10-18)
    if pod == 0 and not chemo:
        sp = [x for x in sp if not any(w in x for w in ("보행", "어제", "제거", "줄"))]
    elif pod == 1:
        sp = [x for x in sp if "어제 제거" not in x]   # yesterday was the op day
    if pod >= 2:
        sp = [x for x in sp if "신경차단" not in x]   # a nerve block wears off on the first day
    sp = [x for x in sp if ("미음" not in x or d == "ld") and ("죽식 진행 여부" not in x or d == "ld") and ("제거" not in x or "제거" not in drain)]
    if drain and "제거" not in drain:   # a drain is being reported: no line saying it was taken out yesterday
        sp = [x for x in sp if not re.search(r"(Hemovac|JP|헤모박|배액관)[^.]*제거", x)]
    sp = coherent_pool(patient.diagnosis, tuple(sp), trauma=False, sex=patient.sex)   # optional line: nothing beats a wrong one (반흔 탈장 "음낭 부종")
    if sp and rng.random() < 0.8:
        form["special"] = _fill(rng.choice(sp), patient, sc)
    else:
        form.pop("special", None)
    special = form.get("special", "")
    if re.search(r"배변|대변|묽은 변|설사|장루", special):   # a stoma patient's output is the stoma line, not "아직 대변 안 보셨습니다"
        form.pop("bowel", None)                  # "배변 아직 없습니다" + "첫 배변 후 통증"
    if "PRN" in special:
        form.pop("prn", None)                    # the same PRN said twice
        if form.get("pain_mgmt") == "pca_prn":
            form["pain_mgmt"] = "pca"
    if chemo and "line" in form:
        line = _fill(str(form["line"]), patient, sc)
        if shift == 23:
            line = line.replace("통해 항암제 주입 중, 포트 바늘", "바늘").replace("통해 항암제 주입 중, ", "")
        form["line"] = line.replace("5-FU 펌프 연결", "5-FU 펌프 연결 중") if "펌프 연결 중" not in line and "펌프 연결 상태" not in line else line
    if not chemo:
        site = rng.choice(_off_operated_side(patient, ["Rt arm", "Lt arm", "Rt hand", "Lt forearm", "Lt hand", "오른팔", "왼팔"]))
        gauge = rng.choice(["20G", "22G", "22G", "24G"])
        when = rng.choice([f"{patient.admission_date} 삽입", f"{patient.op_date} 삽입"] + (["오늘 교환함"] if pod >= 1 else [])) if pod <= 2 \
            else rng.choice(["오늘 교환함", "어제 교환함", "내일 교환 예정"])
        form["line"] = f"{site} {gauge} line 하나, {when}"
    ltube = not chemo and sc is not None and pod <= 1 and any("ltube" in a for a in (sc.form.get("attachments") or []))
    if ltube and rng.random() < 0.4:
        form["other_tube"] = "L-tube 자연 배액 중"
    else:
        form.pop("other_tube", None)
    if not dm and not (chemo and rng.random() < 0.3):
        form.pop("glucose", None)
    if (not abdominal or hi < 5) and "복부" in form.get("imaging", ""):
        form["imaging"] = rng.choice(["chest PA 특이 소견 없음", ""])
    if not form.get("imaging"):
        form.pop("imaging", None)
    form["pressure"] = "risk" if age >= 75 and rng.random() < 0.15 else "none"
    form["delirium"] = "night" if age >= 70 and rng.random() < 0.1 else "none"
    if form["delirium"] == "night" and form["caregiver"] in ("none", "intermittent"):
        form["caregiver"] = rng.choice(["child", "spouse", "caregiver"])   # "야간 섬망 있어 보호자 상주"
    pump = "FOLF" in (patient.regimen or "")
    alone = form["caregiver"] in ("none",)
    if chemo and patient.regimen in ("HP", "H"):
        if re.search(r"ANC", str(form.get("lab") or "")):
            form["lab"] = rng.choice(["크레아티닌 정상 범위", "특이 소견 없음"])
        if "덱사메타손" in str(form.get("glucose") or ""):
            form.pop("glucose")
        if "항구토제" in str(form.get("prn") or ""):
            form.pop("prn")
    pend = [x for x in _pool(sc, "pending", "s5") if ("미음" not in x or d in ("npo", "sow")) and ("퇴원" not in x or near_dc) and ("펌프" not in x or pump)
            and not (alone and "보호자" in x) and _fits_shift(x, shift, "pending")
            and not (patient.regimen in ("HP", "H") and "항구토제" in x)]
    if pend:
        form["pending"] = _fill(rng.choice(pend), patient, sc)
    else:
        form.pop("pending", None)
    plans = [x for x in _pool(sc, "plan", "s5") if "수술 준비" not in x and ("PICC" not in x or "PICC" in form.get("line", ""))
             and ("퇴원" not in x or near_dc) and ("폐활량계" not in x or (pod <= 2 and abdominal and hi >= 4)) and ("펌프" not in x or pump)
             and ("항구토제" not in x or "항구토제" in form.get("prn", "")) and _fits_shift(x, shift, "plan")]
    if "퇴원" in special and not chemo and near_dc:
        plans = [x for x in ("퇴원 교육 시행", "퇴원 처방 확인") if _fits_shift(x, shift, "plan")]
    if not plans:   # something the next shift really does (2026-10-18)
        plans = [{7: "오전 회진 후 처방 확인", 15: "저녁 활력징후와 통증 재사정", 23: "새벽 활력징후 확인과 아침 채혈"}[shift]]
    form["plan"] = _fill(rng.choice(plans), patient, sc)
    if form.get("pending") and re.search(r"CBC|퇴원|펌프|항구토제|랩", form["pending"]) and \
            re.search(r"CBC|퇴원|펌프|항구토제|랩", form["plan"]) and \
            set(re.findall(r"CBC|퇴원|펌프|항구토제|랩", form["pending"])) & set(re.findall(r"CBC|퇴원|펌프|항구토제|랩", form["plan"])):
        form.pop("pending")                      # the same task as pending and as plan
    # lab line: varied numbers that fit the day (the same "WBC 11.2, CRP 8.5로 어제보다 상승" was in 18% of handovers, on POD 0 too)
    if not chemo and form.get("lab") in TEXT_POOLS["lab"]:
        form["lab"] = f"수술 후 Hb {rng.uniform(9.6, 12.8):.1f}" if pod == 0 else rng.choice([
            f"WBC {rng.uniform(7.5, 12.5):.1f}, CRP {rng.uniform(1.5, 9.0):.1f}(으)로 어제보다 감소한 상태", f"Hb {rng.uniform(9.0, 12.5):.1f}(으)로 어제와 비슷한 수준",
            f"K {rng.uniform(3.1, 3.4):.1f}(으)로 감소해 KCl 추가 처방된 상태", "특이 소견 없음"])
    if "크레아티닌" in special and "크레아티닌" in str(form.get("lab") or ""):
        form.pop("lab")
    if pod == 0 and not chemo and "어제" in str(form.get("lab") or ""):
        form["lab"] = form["lab"].replace("어제보다", "수술 전보다")
    if form.get("transfusion"):
        form["lab"] = f"수혈 전 Hb {rng.uniform(6.8, 7.9):.1f}"   # 2026-10-18: "PRBC 1 pack 수혈 완료" + "랩 특이 소견 없어요"
    if pod == 0 and "CT" in str(form.get("imaging") or ""):
        form.pop("imaging")


def _fits_shift(text: str, shift: int, kind: str) -> bool:
    """Can the shift that hears this handover line use it? kind: plan (a task for the next shift) | pending | special (status).
    2026-10-18 검수: 15시에 "오전 외래 CT 이송 준비", 23시에 "퇴원 교육 시행", 07시에 "방광 세척 오늘 오후 중단함"."""
    if re.search(r"(오늘|당일) 퇴원", text):
        return shift == 7
    if "퇴원 교육" in text:
        return shift in (7, 15)
    if kind in ("plan", "pending") and re.search(r"내일 (아침|오전)", text):
        return shift == 23               # only the night shift is there tomorrow morning
    if kind in ("plan", "pending") and re.search(r"(?<!내일 )(오전|아침)", text):
        return shift != 15
    if "오늘 오후" in text:
        return shift == 23
    if kind == "special" and "오늘" in text and "예정" not in text:
        return shift != 7                # something done today is not news at 07:00
    return True


def _section_on(form: dict[str, Any], t, key: str) -> bool:
    sec = next((s for s in t.sections if s.key == key), None)
    return sec is not None and any(form.get(f.key) is True for f in sec.fields if f.kind == "bool")


def _drop_section(form: dict[str, Any], t, key: str) -> None:
    for sec in t.sections:
        if sec.key == key:
            for f in sec.fields:
                form.pop(f.key, None)


def _derive_s6(form: dict[str, Any], patient: Patient, sc, rng: random.Random, t) -> None:
    """Progress record: the morning pain decides the plan, the plan decides the afternoon reassessment, and the
    charting checklist (the only record that carries one) only lists protocols this patient could have."""
    age = patient.age or 50
    chemo = patient.kind == "chemo"
    pod = patient.pod or 0
    night = form.get("night", "slept")
    if chemo and night == "pain_wake":
        night = form["night"] = "restless"
    mute = sc is not None and sc.key == "Tracheostomy"   # a fresh cuffed tracheostomy (POD 1-3) is charted from observation
    if mute:
        night = form["night"] = "slept_obs"
        form.pop("pain_desc", None)
    form["nrs1"] = rng.choice([0, 0, 1, 2]) if chemo else rng.randint(*{"slept": (1, 3), "pain_wake": (4, 7), "restless": (2, 5)}.get(night, (1, 3)))
    pca_ok = not chemo and pod <= 2 and sc is not None and any("pca" in x for x in (sc.form.get("pain_mgmt") or []))
    # 2026-10-17 대량 검수: PRN은 NRS 4 이상에만 ("NRS 2점, PRN 투여"), NRS 0이면 "추가적인 중재 원하지 않음"도 없음
    if chemo:
        form["pain_plan"] = "prn" if form["nrs1"] >= 4 else "explain"
    elif form["nrs1"] >= 5:
        form["pain_plan"] = "pca" if pca_ok and rng.random() < 0.5 else "prn"
    else:
        form["pain_plan"] = "pca" if pca_ok and rng.random() < 0.5 else ("prn" if form["nrs1"] >= 4 and rng.random() < 0.5 else "explain")
    form["pca_remove"] = ("removed" if pod >= 1 and rng.random() < 0.6 else "keep") if form["pain_plan"] == "pca" else "na"
    # the 07:00 PRN is re-assessed 30 minutes later (d_prn), so the 13:30 entry is the PCA removal or a routine check
    form["reassess"] = "after_pca" if form["pca_remove"] == "removed" else "stable"
    clock = {"오전 7시": ("오전 7시 30분", "오전 8시"), "오전 7시 10분": ("오전 7시 40분", "오전 8시 10분"), "오전 7시 30분": ("오전 8시", "오전 8시 10분")}
    form["t1"] = rng.choice(list(clock))
    if form["pain_plan"] == "prn":
        form["t1p"] = clock[form["t1"]][0]
        form["nrs_prn"] = max(0, form["nrs1"] - rng.randint(2, 4))
    else:
        form.pop("t1p", None), form.pop("nrs_prn", None)
    base = form.get("nrs_prn", form["nrs1"])
    form["nrs4"] = min(3, max(0, form["nrs1"] - rng.randint(2, 4))) if form["reassess"] == "after_pca" else min(base, rng.randint(0, 3))   # "PCA 제거 후에도 조절 잘 됨" at 3 or less
    if form["nrs1"] == 0:
        form.pop("pain_desc", None)       # no "어디가 아프다" at NRS 0
        if form["pain_plan"] == "explain":
            form.pop("pain_plan")         # nothing to decline at NRS 0
    elif "신경차단" in str(form.get("pain_desc") or "") and pod >= 2:   # a nerve block wears off on the first day
        pool = [x for x in (sc.pools.get("pain_desc") if sc is not None else ()) if "신경차단" not in x] or ["수술 부위 쑤시는 느낌"]
        form["pain_desc"] = rng.choice(pool)
    form["vitals"] = random_vitals(rng, "normal", with_spo2=True)   # the 7 o'clock round of a stable patient
    # meals follow one diet for the day (2026-10-17 대량 검수: 아침 전량 섭취 → 점심·저녁 금식, 치핵 POD 3 종일 금식)
    abdominal = not chemo and sc is not None and sc.form.get("abdomen", 1) is not None
    diet = _diet_for_day(sc, pod, rng) if abdominal else "gd"
    if mute:
        diet = rng.choice(sc.form.get("s5.diet") or ["soft"])   # 경관식·연식·미음, not 일반식 the day after a tracheostomy
    if diet in ("npo", "sow", "tf"):
        form["meal1"] = form["meal2"] = diet
    else:
        form["meal_kind"] = {"ld": "미음", "sd": "죽", "soft": "죽"}.get(diet, "당뇨식" if "당뇨" in patient.diagnosis else "일반식")
        form["meal1"] = rng.choices(["all", "half", "little"], weights=[6, 3, 1])[0]
        form["meal2"] = rng.choices(["all", "half"], weights=[7, 3])[0]
    if diet in ("npo", "sow") and re.search(r"KVO|40cc/hr", str(form.get("fluid") or "")):
        form["fluid"] = rng.choice(["하트만 1리터 80cc/hr", "하트만 1리터 60cc/hr"])   # nothing by mouth: a maintenance rate, not KVO (2026-10-18)
    if pod >= 1 or chemo:
        form["vitals"]["o2"] = "room air"
    form["fall"] = rng.random() < 0.8
    hi_fall = age >= 70 or (patient.department == "정형외과" and age >= 60) or any(w in patient.diagnosis for w in _TRAUMA) \
        or (sc is not None and (sc.key in ("THA", "TKA", "BKA") or (sc.form.get("fall") or []) == ["high"]))   # 기관절개 POD 2 "혼자 복도 보행"
    # --- afternoon / evening entries (user 2026-10-17: 그날 있었던 기록을 시간대별로) ---
    if chemo:
        form["afternoon_activity"] = "chemo_infusion"
    elif sc is not None and sc.key == "BKA":
        form["afternoon_activity"] = "bedrest" if pod <= 1 else "wheelchair"   # no corridor walk before a prosthesis (2026-10-18)
    else:   # a high fall-risk patient (77세 TKA POD 2) does not walk the corridor alone
        form["afternoon_activity"] = "sit" if pod == 0 else ("walk_assist" if pod == 1 or hi_fall else rng.choice(["walk_assist", "walk_self"]))
    if not chemo and _scenario_drains(sc) and pod <= 3:
        form["p_drain_color"] = col = rng.choice(["serosanguineous", "serous"])   # the checklist reads the same drain (2026-10-18: 어깨 Hemovac "bilious")
        form["drain_note"] = f"{'Hemovac' if patient.department == '정형외과' else 'JP'} 배액 {col} {rng.randint(10, 80)}cc 비우고 양상 관찰함"
    elif not chemo and pod <= 1 and sc is not None and "keep" in (sc.form.get("foley") or []):
        form["drain_note"] = "소변줄 통해 소변 straw하게 시간당 50cc 이상 나옴"
    elif rng.random() < 0.5:
        form["drain_note"] = rng.choice(["자가배뇨 양호함", "배뇨 불편감 없음"])
    else:
        form.pop("drain_note", None)
    form["vitals_evening"] = random_vitals(rng, "normal", with_spo2=False)
    form["evening_note"] = rng.choices(["stable", "visit", "edu", "pain_prn"], weights=[55, 20, 15, 10])[0]
    if form["evening_note"] == "pain_prn" and form.get("pain_plan") == "pca" and form["pca_remove"] == "keep":
        form["evening_note"] = "stable"               # a running PCA is not topped up with PRN
    # Evening/Night (user 2026-10-17: 세 듀티의 정규 라운딩 + 이벤트); the clock keeps the three roundings at 07:xx, 15:xx, 23:xx
    form["t2"] = clock[form["t1"]][1]
    form["t3"] = rng.choice(["오후 12시 30분", "오후 12시 40분", "오후 1시"])
    form["t4"] = rng.choice(["오후 1시 30분", "오후 2시"])
    form["t5"] = rng.choice(["오후 3시", "오후 3시 10분", "오후 3시 20분"])
    form["t6"] = rng.choice(["오후 6시", "오후 6시 10분"])
    form["t7"] = rng.choice(["오후 8시", "오후 8시 30분", "오후 9시"])
    form["t8"] = rng.choice(["오후 11시", "오후 11시 10분", "오후 11시 30분"])
    form["vitals_night"] = random_vitals(rng, "normal", with_spo2=False)
    form["nrs_n"] = min(int(form["nrs4"]), rng.randint(0, 3))
    if form["evening_note"] == "pain_prn":
        form["nrs_n"] = max(form["nrs_n"], 1)
    pca_running = form.get("pain_plan") == "pca" and form["pca_remove"] == "keep"
    awake_w = 10 if form["nrs_n"] >= 3 and not (mute or pca_running) else 0
    form["night_onset"] = rng.choices(["asleep", "resting", "awake_pain", "hypnotic"], weights=[60, 25, awake_w, 8 if age >= 65 else 2])[0]
    if form["night_onset"] == "awake_pain":
        form["nrs_n"] = max(form["nrs_n"], 4)
    elif form["night_onset"] in ("asleep", "hypnotic"):
        form.pop("nrs_n", None)   # nobody scores the pain of a sleeping patient (2026-10-18 2차 검수: 70%)
        form.pop("vitals_night", None)   # 23시 수면 중: 통증 수면 중임·Good sleep pattern·주입 속도·IV site (user 2026-10-18)
    form["night_line"] = True                # the night round always checks the running infusion and the IV site
    # --- charting checklist: only protocols this patient can have, with details taken from the record ---
    # the 07:00 round already charts sleep, meal, V/S, pain and the bed/rail/wheel check: a random record does not repeat
    # them as Routine / 환경관리 / 급성통증 checklist entries at 08:30 (2026-10-17 대량 검수: "뒤척이며 깊게 못 잤다" → 08:30
    # "수면양상 관찰함, 특이사항 없이 잘 잤다고 함"); the user can still tick them by hand
    for key in ("prot_routine", "prot_fall_low", "prot_apain"):
        _drop_section(form, t, key)
    if not hi_fall:
        _drop_section(form, t, "prot_fall_high")
    elif form["fall"]:
        form.pop("p_fall_intervene", None)   # the round said 침대 높이·난간·바퀴 already
    if age < 70 and not (sc is not None and sc.key in ("BKA", "THA")):
        _drop_section(form, t, "prot_skin")
    if age < 60 or rng.random() < 0.5:
        _drop_section(form, t, "prot_glucose")
    elif form.get("p_hypo_intervene") and rng.random() < 0.7:
        form.pop("p_hypo_intervene")      # hypoglycaemia is the rare branch
    if chemo or not _scenario_drains(sc):
        _drop_section(form, t, "prot_drain")
    elif _section_on(form, t, "prot_drain"):
        form["p_drain_type"] = "Hemovac" if patient.department == "정형외과" else "JP"
        form["p_drain_site"], form["p_drain_date"] = "수술 부위", patient.op_date
        if form.get("p_drain_remove"):     # removed in the morning: low output, and the evening round has no drain to empty
            form["p_drain_amount"] = rng.randrange(10, 35, 5)
            form["drain_note"] = f"{form['p_drain_type']} 제거 부위 드레싱 깨끗하고 삼출물 없음"
    foley_ok = not chemo and sc is not None and "keep" in (sc.form.get("foley") or []) and pod <= 1
    if not foley_ok:
        _drop_section(form, t, "prot_foley")
    elif _section_on(form, t, "prot_foley"):
        form["p_foley_date"], form["p_foley_type"] = patient.op_date, "Foley catheter"
        form["p_urine_color"] = "pinkish하게" if sc.key == "TURB" else rng.choice(["straw하게", "straw하게", "orange 색깔로"])
        voided, scanned = form.pop("p_self_void", None), form.pop("p_residual_check", None)
        if voided or scanned:
            form["p_foley_remove"] = True    # the void comes hours after the 08:30 removal: the evening round says it
        if form.get("p_foley_remove") and "소변줄" in str(form.get("drain_note") or ""):
            form["drain_note"] = "소변줄 제거 후 자가배뇨 양호함"
    if form.get("pain_plan") != "pca":
        for k in [k for k in form if k.startswith("p_pca_")]:
            form.pop(k)
    else:
        form.pop("p_pca_end", None)          # e3 already says whether the PCA came out
    if chemo:
        _drop_section(form, t, "prot_breath")
    elif _section_on(form, t, "prot_breath"):
        form["p_rr"], form["p_spo2"] = form["vitals"].get("rr", 18), form["vitals"].get("spo2") or 98   # same numbers as the round
        form["p_breath_sound"] = rng.choices(["양측 깨끗함", "하부 감소됨"], weights=[8, 2])[0]   # a stable ward patient, not 수포음 without action
        form["p_accessory"] = "없음"         # RR 17, room air 98 (2026-10-18: "호흡보조근 사용 있음" with no action)
        if mute:
            form.pop("p_spirometer", None)  # nobody blows into an incentive spirometer through a tracheostomy
    # nausea needs a reason: chemotherapy or a running PCA (2026-10-17: ORIF 환자에 "흡인 예방 위해 측위 유지")
    if not (chemo or form.get("pain_plan") == "pca"):
        _drop_section(form, t, "prot_nausea")
    elif _section_on(form, t, "prot_nausea"):
        form["p_nv_note"] = "PCA 관련 오심" if not chemo else rng.choice(["오심만 있고 구토 없음", "구토 1회", "식후 오심"])
        form["p_nausea_assess"] = form["p_antiemetic_give"] = True   # "항구토제 투여 후 안정됨" needs the assessment and the drug
        if form["meal1"] in ("npo", "sow", "tf"):
            form.pop("p_diet_adjust", None)  # nothing to hold
        elif form.get("p_diet_adjust"):
            form["meal2"] = "half"           # "소량씩 자주" / "식사 보류" → a smaller lunch, not 금식
    if pod >= 1 or chemo:
        form.pop("p_ast", None)              # the skin test was done before the first dose
    if form["meal1"] in ("npo", "sow"):
        _drop_section(form, t, "prot_glucose")
    if _section_on(form, t, "prot_glucose"):
        # 2026-10-17 대량 검수: "BST 아침 식전 380" at 09:00 after breakfast, "380 → 341로 안정됨", 380 with education only.
        # The check is two hours after breakfast (generator puts it at 10:15); 200 or more gets sliding-scale RI.
        form["p_bst"], form["p_bst_time"] = True, "점심 식전"   # QID 06·12·17·21시 (매 식전 + 자기 전)
        v = form["p_bst_value"] = rng.choice([rng.randint(130, 199), rng.randint(130, 199), rng.randint(200, 280)])
        form["p_glucose_sx"] = "증상 없음" if v < 250 else rng.choice(["증상 없음", "갈증·다뇨"])
        if v >= 200:
            form["p_insulin_give"], form["p_insulin"], form["p_insulin_scheme"] = True, "RI", "sliding scale"
            form["p_insulin_unit"] = 2 if v < 250 else 4
        else:
            form.pop("p_insulin_give", None)
        for k in ("p_hypo_intervene", "p_bst_recheck", "p_glucose_noti"):
            form.pop(k, None)
    if chemo and "케모포트" not in str(form.get("line") or ""):
        if "케모포트" in str(form.get("pain_desc") or ""):
            form["pain_desc"] = rng.choice([x for x in (sc.pools.get("pain_desc") or ()) if "케모포트" not in x] or ["명치 쪽 더부룩한 느낌"])
        if "PICC" in str(form.get("line") or "") and "케모포트" in str(form.get("wound") or ""):
            form["wound"] = "PICC 삽입 부위"
    form.pop("p_o2_apply", None)   # the rounds chart room air all day (2026-10-17: 08:30 "SpO2 저하되어 reservoir mask 4L")
    if form.get("line"):
        ok_line = _off_operated_side(patient, TEXT_POOLS["s6.line"] + [form["line"]], str(form.get("wound") or ""))
        if form["line"] not in ok_line:
            form["line"] = rng.choice(ok_line)
    line = str(form.get("line") or "")
    m = re.search(r"(\d\d)\s*(?:G|게이지)", line)
    if m and f"{m.group(1)}G" in ("18G", "20G", "22G", "24G"):
        form["p_iv_gauge"] = f"{m.group(1)}G"
        form["p_iv_site"] = line[: m.start()].strip() or "Lt arm"
    if form.get("wound"):
        form["p_wound_site"] = form["p_dsg_site"] = form["p_dsg_site2"] = form["wound"]
    else:
        _drop_section(form, t, "prot_wound")   # ESS / chemo: nothing to dress
    if _section_on(form, t, "prot_wound"):
        # the round already looked at the wound ("드레싱 깨끗하고 건조함"); the checklist adds the dressing change and teaching
        for k in ("p_wound_obs", "p_dressing_check"):
            form.pop(k, None)
        form["p_dsg_by"] = rng.choice(["주치의", "주치의", "담당 간호사"])
    if _section_on(form, t, "prot_med"):
        for k in ("p_inf_rate", "p_iv_site_check"):   # fluid and IV site were charted at 07:00 (5DW → "하트만 1L" mismatch)
            form.pop(k, None)
    if form.get("p_culture_do"):
        form["p_fever_noti"] = True          # cultures are drawn on the doctor's order
    form["p_apain_scale"] = form["p_cpain_scale"] = "NRS"
    form["p_iv_patency"] = "양호함" if rng.random() < 0.9 else form.get("p_iv_patency", "양호함")
    if chemo:
        form["p_med_name"] = rng.choice(["온단세트론 8mg", "덱사메타손 10mg", "아프레피탄트 125mg"])
        form.pop("p_ast", None)
    form["p_meal_note"] = {"all": "all", "half": "half", "little": "little"}.get(form["meal1"], "npo")
    if rng.random() < 0.8:
        form["p_status_note"] = "stable"
    if _section_on(form, t, "prot_fever"):
        # 2026-10-17: "38.7도로 발열 확인" then nothing, and still 38.7 at noon
        form["p_temp_measure"] = form["p_antipyretic_give"] = form["p_temp_recheck"] = True
        if chemo or rng.random() < 0.7:
            form["p_fever_noti"] = True      # a febrile chemo patient is always reported (neutropenia)
        # the 07:00 round saw a clean wound; a chemo patient has none (2026-10-18: E-FOLFIRI "수술 부위" 사정, wound culture)
        form["p_fever_sx"] = rng.choice(["오한 있음", "기침·객담", "특이 증상 없음"] if chemo else ["오한 없음", "오한 있음", "기침·객담", "배뇨통", "특이 증상 없음"])
        form["p_culture"] = {"기침·객담": "sputum culture", "배뇨통": "urine culture"}.get(form["p_fever_sx"], "blood culture 2쌍")
        form["p_recheck_temp"] = round(max(37.0, float(form.get("p_temp") or 38.4) - rng.uniform(0.5, 1.2)), 1)   # not 38.7 → 36.8 in an hour
        recheck = float(form["p_recheck_temp"])
        form["bt3"] = round(rng.uniform(36.6, max(36.7, min(37.4, recheck))), 1)
    else:
        form["bt3"] = round(rng.uniform(36.3, 37.4), 1)
    # dinner follows the final lunch state (the 오심 protocol may have made lunch 금식 above)
    form["meal3"] = form["meal2"] if form["meal2"] in ("npo", "sow", "tf") else rng.choices(["all", "half"], weights=[7, 3])[0]

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
    if template_key == "s1" and vs and float(vs.get("bt") or 36.5) >= 38.0 and not any(w in cc + str(patient.diagnosis if patient else "") for w in ("발열", "오한", "호중구", "염", "감염", "농양")):
        issues.append("발열이 있는데 주호소·진단에 열 날 이유가 없음")
    if template_key == "s3_1" and patient is not None and patient.pod is not None and form.get("timing") in ("day0", "pod1", "pod2"):
        if {"day0": 0, "pod1": 1, "pod2": 2}[form["timing"]] != patient.pod:
            issues.append("기록 시점(수술 당일/POD)이 환자의 POD와 다름")
    if template_key == "s3_1" and form.get("consciousness") == "drowsy" and form.get("responds"):
        issues.append("의식 기면인데 질문에 적절히 대답")
    if template_key == "s3_1" and vs and "o2" in form and (form["o2"] == "none") != (str(vs.get("o2") or "room air") == "room air"):
        issues.append("산소 적용 항목과 활력징후의 산소가 다름")
    if template_key == "s3_2" and vs:
        ev = form.get("event")
        if ev == "발열" and float(vs.get("bt") or 0) < 37.8:
            issues.append("발열 기록인데 체온이 정상")
        if ev == "통증" and int(form.get("nrs") or 0) < 5:
            issues.append("통증 기록인데 통증 점수가 낮음")
        rv = form.get("re_vitals") if isinstance(form.get("re_vitals"), dict) else None
        if ev == "발열" and form.get("response") == "improved" and rv and float(rv.get("bt") or 0) >= 38.0:
            issues.append("호전이라는데 재측정 체온이 여전히 높음")
        if ev not in ("출혈", "배액 이상") and form.get("recheck") == "no_change":
            issues.append("출혈·배액 기록이 아닌데 드레싱·배액 재확인 문구")
    if template_key == "s5":
        if form.get("diet") == "npo" and form.get("gas_out") is True:
            issues.append("금식인데 가스 배출 후 물 시작")
        if form.get("diet") in ("sd", "gd", "soft", "dm") and "gas_out" in form:
            issues.append("일반식인데 가스 배출 이야기")
        if form.get("vs_summary") == "fever" and float(form.get("bt_now") or 0) < 38.0:
            issues.append("발열 지속인데 현재 체온이 정상")
        if form.get("vs_summary") == "fever_resolved" and float(form.get("bt_now") or 0) >= float(form.get("bt_peak") or 99):
            issues.append("열 떨어졌다는데 현재 체온이 최고 체온 이상")
        if patient is not None and patient.kind != "chemo" and form.get("glucose") and "dm" not in (form.get("history") or []):
            issues.append("당뇨가 없는데 혈당 관리 이야기")
        if "PICC" in str(form.get("plan") or "") and "PICC" not in str(form.get("line") or ""):
            issues.append("PICC가 없는데 PICC 드레싱 계획")
    if template_key == "s6":
        if form.get("reassess") == "after_pca" and form.get("pca_remove") != "removed":
            issues.append("PCA 제거 후 재사정인데 PCA를 제거하지 않음")
        if form.get("reassess") == "after_prn" and form.get("pain_plan") != "prn":
            issues.append("PRN 후 재사정인데 PRN 투여가 없음")
        if form.get("reassess") != "stable" and int(form.get("nrs4") or 0) >= int(form.get("nrs1") or 0):
            issues.append("중재 후 재사정 점수가 아침 점수 이상")
        if form.get("meal1") == "npo" and form.get("meal2") in ("all", "half"):
            issues.append("아침 금식인데 점심 식사")
    if template_key == "s4" and patient is not None:
        if form.get("report_edu") in ("op", "chemo") and (form["report_edu"] == "chemo") != (patient.kind == "chemo"):
            issues.append("알려야 할 상황 교육이 환자 종류와 다름")
        for generic, note in (("wound", "wound_note"), ("diet_edu", "diet_note"), ("activity", "activity_note"), ("device", "device_note")):
            if form.get(generic) and form.get(note):
                issues.append(f"{generic} 일반 문장과 수술별 문장이 같이 있음")
        if form.get("further") in ("chemo", "rt", "pending_path") and not any(w in patient.diagnosis for w in ("암", "종양", "전이", "증식", "림프", "종괴")):
            issues.append("양성 질환인데 보조 항암·방사선 계획")
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
    if template_key == "s1" and "fall_history" in form and any(w in cc for w in ("낙상", "미끄러", "넘어")) and form["fall_history"] != "yes":
        issues.append("낙상으로 입원했는데 낙상력 없음")
    return issues


def random_form(template_key: str, rng: random.Random, patient: Patient | None = None) -> dict[str, Any]:
    """Random form that passes ``audit`` (re-drawn up to 6 times; the derivations make this rare)."""
    form = _random_form_once(template_key, rng, patient)
    for _ in range(5):
        if not audit(form, patient, template_key):
            break
        form = _random_form_once(template_key, rng, patient)
    return form


# --- discharge leaflet → category (user 2026-10-17: 퇴원 교육은 범주별로 한 번) -------------------------------------
_LEAFLET_KEY = {"wound": "wound_note", "device": "device_note", "diet": "diet_note", "activity": "activity_note",
                "report": "report_note", "opd": "opd_note", "precautions": "precautions"}
_LF_WOUND = r"상처|드레싱|소독|샤워|통목욕|실밥|스테플|접착제|테이프|흉터|패킹"
_LF_DEVICE = r"배액|장루|PICC|보형물|확장기|소변줄|소변백|카테터|스토마|기관절개관|흡인|내관|펌프"
_LF_REPORT = r"내원|응급실|연락|문의|병원 방문|병원으로|알리도록|알리시|오시"
_LF_DIET = r"식사|식이|음식|먹|섭취|수분|날 것|맵|금주|(?<!수)술|치료식|지사제|로페라마이드"
_LF_ACT = r"운동|무거운|걷|활동|운전|복직|체중 부하|목발|보행|가사|달리기|수영|워커|부하|일상생활|양반다리|쪼그려"
_LF_OPD = r"외래|조직검사|결과|문자|납부|원무|추적|방사선|심초음파|주사 일정|제거 예정|결정"


def leaflet_category(x: str) -> str:
    head = x[:14]
    if re.search(r"사우나|대중탕|통목욕|탕 목욕", x):
        return "wound"                     # bathing replaces the generic "탕 목욕은 외래까지" (2026-10-18: 두 가지 기간)
    if re.search(_LF_DEVICE, head):
        return "device"
    if re.search(_LF_WOUND, head):
        return "wound"
    if re.search(_LF_REPORT, x) and re.search(r"면|시 |경우|땐|때|지속", x):
        return "report"
    if re.search(_LF_WOUND, x):
        return "wound"
    if re.search(_LF_DEVICE, x):
        return "device"
    if re.search(_LF_DIET, x):
        return "diet"
    if re.search(_LF_ACT, x):
        return "activity"
    if re.search(_LF_OPD, x):
        return "opd"
    return "precautions"


def _spread_leaflet(form: dict[str, Any], rng: random.Random, patient: Patient, sc, sc_pools: dict[str, Any]) -> None:
    """Two or three ward-leaflet items per discharge record, each filed under its category (one sentence per category)."""
    pool = sc_pools.get("s4.leaflet") or ()
    if pool and patient is not None:
        pool = coherent_pool(patient.diagnosis, tuple(pool), trauma=False, sex=patient.sex) or list(pool)
    if pool and sc is not None and sc.key == "LAR":   # stoma care and reversal only with a stoma, LARS advice only without (2026-10-18)
        stoma = form.get("device") == "stoma"
        pool = [x for x in pool if ("장루" in x) == stoma] or list(pool)
    if not pool:
        return
    k = min(len(pool), rng.choice([1, 2, 2, 3]))
    for x in rng.sample(list(pool), k):
        key = _LEAFLET_KEY[leaflet_category(x)]
        sent = formal_from_chart(_fill(x, patient, sc).rstrip(".") + ".").rstrip(".")   # "교육함" -> "교육하였습니다"
        form[key] = f"{form[key]}. {sent}" if form.get(key) else sent


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
            if pool and sc is not None and (f"{template_key}.{f.key}" in sc_pools or f.key in sc_pools):
                pool = coherent_pool(patient.diagnosis, tuple(pool), trauma=False, sex=patient.sex) or list(pool)   # 좌측 손목 골절 ↔ "발목 올리기" 금지
            if pool and f.key == "special_edu":
                pool = [x for x in pool if "장루 교환" not in x and "장루 관리" not in x] or list(pool)   # the 장치 관리 item says it
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
        def _by_age(cands):   # 2026-10-18: 64세 "생리 양이 많았어요" + 폐경됨, 48세 "폐경 후 질 출혈" + 월경일
            age = patient.age or 50
            return [x for x in cands if not (age >= 52 and re.search(r"생리|월경|가임|임신 계획", x)) and not (age < 50 and "폐경" in x)] or list(cands)
        if "chief_complaint" in form:
            pool = _by_age(coherent_pool(patient.diagnosis, sc.cc) or list(sc.cc))
            pool = [x for x in pool if first or "1차 시작" not in x] or pool   # "보조 항암 1차 시작" only on cycle 1
            form["chief_complaint"] = _fill(rng.choice(pool), patient, sc)
        cc = form.get("chief_complaint", "")
        if "present_illness" in form:
            pool = _by_age(coherent_pool(patient.diagnosis, sc.pi) or list(sc.pi))
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
                if "예정" in form.get("present_illness", ""):
                    form.pop("plan", None)               # "N차 예정" said twice
                else:
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
                if re.search(r"낙상|미끄러|넘어|사고|압궤|골절", cc):
                    form["onset"] += " 다치심"     # an injury: "2일 전 다치셨습니다", not "2일 전 시작되었다고 하십니다"
            elif any(w in cc for w in ("검진", "우연히", "발견", "추적", "재발", "전이", "소견", "상담", "BRCA", "예방적")) or \
                    re.search(r"(입원|예정|결정|진단|위해|교체|재건|권유|의뢰)\s*$|진통|분만|\d+\s*(개월|주|년|일)\s*전|부터", cc) or \
                    re.search(r"수개월|수년|\d+\s*(회|주|개월|년|일)(?!\s*전)|제왕절개", cc):
                form.pop("onset", None)          # a decision, a dated complaint or "혈뇨 1회·2주·수개월간" has no "N개월 전부터" (2026-10-18)
            elif "onset" in form:
                opts = {"1개월 전부터": 1, "2개월 전부터": 2, "3개월 전부터": 3, "6개월 전부터 서서히": 6, "1년 전부터": 12}
                tried = re.search(r"치료\s*(\d+)\s*개월|(\d+)\s*개월\s*(간\s*)?(치료|반응)", form.get("present_illness", ""))
                floor = int(tried.group(1) or tried.group(2)) if tried else 0   # "약물 치료 3개월 반응 없어" → the complaint is older than 3 months
                form["onset"] = rng.choice([k for k, v in opts.items() if v > floor] or ["1년 전부터"])
        _apply_scenario(form, template_key, {f.key: f for _, f in t.iter_fields()}, sc, rng)
    if template_key == "s4":
        _spread_leaflet(form, rng, patient, sc, sc_pools)   # before _consistency, so _derive_s4 can drop the generic twin
    _consistency(form, template_key, t, rng, patient, sc)
    if template_key == "s1" and patient is not None:
        female = patient.sex.startswith("여")
        if not female and rng.random() < 0.5:
            form.pop("marital", None)
        # the ward asks LMP only of gynecologic surgery patients (user, 2026-10-16); C-sec has no LMP talk
        if female and patient.kind == "op" and patient.department == "산부인과" and patient.surgery != "C-sec":
            m = re.match(r"(\d+)월", patient.admission_date or "")
            month = int(m.group(1)) if m else 10
            adm = _month_day(patient.admission_date or "")
            last = (datetime(2026, *adm) if adm else datetime(2026, month, 15)) - timedelta(days=rng.randint(3, 35))   # before the admission
            form["lmp"] = "폐경됨" if (patient.age or 0) >= 52 else f"{last.month}월 {last.day}일"   # "폐경됨" → "폐경되셨습니다", not "월경일은 폐경 상태입니다"
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
