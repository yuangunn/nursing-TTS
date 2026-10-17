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
    "npo_meds": ["혈압약은 아침 6시 소량의 물로", "갑상선약은 아침 소량의 물로"],
    "prep_detail": ["오늘 저녁 8시 하제 복용 예정", "수술 당일 아침 관장 예정", "클리퍼 제모 시행함"],
    "duration": ["3~4시간", "2시간", "1시간 30분", "4~5시간"],
    "blood_type": ["A형 Rh+", "B형 Rh+", "O형 Rh+", "AB형 Rh+", "A형 Rh-"],
    "question": ["수술 후 식사 시작 시점 질문하여 가스 배출 후 물부터 단계적으로 진행한다고 설명함", "통증이 얼마나 심한지 질문하여 PCA로 조절 가능하다고 설명함",
                 "입원 기간 질문하여 수술 후 경과 보고 결정된다고 설명함", "수술 후 언제부터 걸을 수 있는지 질문하여 다음 날부터 보행 시작한다고 설명함"],
    "arrival_time": ["12시 30분", "오후 2시", "오전 11시 50분", "오후 4시 20분"],
    "vs_lead": ["도착 당시", "병실 도착 후", "오후 2시"],
    "iv": ["Lt arm 20G line", "Rt hand 22G line", "Lt forearm 22G IV line", "Rt arm 20G IV line", "Lt hand 24G line", "Rt forearm 20G line"],
    "p_iv_site": ["Lt arm", "Rt hand", "Lt forearm", "Rt arm", "왼팔", "오른손등"],
    "found_time": ["오전 10시", "오후 2시", "오후 6시", "새벽 3시", "오후 9시 30분"],
    "complaint": ["열감 조금 있다고 표현하고 오한은 없음", "오한 있다고 하심", "열감 없다고 하나 얼굴 붉어짐", "두통 호소"],
    "drain": ["JP 배액 serosanguineous 양상 40cc", "JP sanguineous 20cc", "JP serous 15cc", "배액관 없음",
              "우측 복부 JP 배액은 장액성으로 색 옅어지고 있음", "JP serosanguineous하게 30cc, 특이 변화 없음"],
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
    "line": ["Rt arm 22G line 하나, 오늘 교환함", "Lt arm 20G line 하나, 오늘 교환함", "오른팔 말초 라인 하나, 오늘 교환함", "Lt hand 22G IV line 하나, 주입 잘 됨"],
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
    pod = {"s1": None, "s2": None, "s3_1": 0, "s3_2": rng.choice([1, 2, 3]),
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
        shift = 23 if form.get("gas_out") else rng.choice([7, 15, 23])   # "금일 가스 아웃 … 저녁부터 물 시작했고" is a night handover
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
    s += {"device": 2, "assist": 4, "wheelchair": 2}.get(mobility or form.get("adl") or "", 0)
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
        elif forced == {"low"} and score > 5:      # make the facts low-risk instead of faking the number (score must match the form)
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


def coherent_pool(dx: str, cands: tuple[str, ...], trauma: bool = True) -> list[str]:
    """Complaints/histories that do not contradict the diagnosis: same side (우측 유방암 ↔ 좌측 멍울),
    same trauma-ness (골관절염 ↔ 낙상 후 통증) and no other aetiology from the same exclusive group
    (대퇴골 경부 골절 ↔ 골관절염으로 치환술 예정).  Empty when nothing fits."""
    side = next((x for x in _SIDES if x in dx), None)
    is_trauma = any(w in dx for w in _TRAUMA)
    groups = [(g, m) for g in _EXCLUSIVE if (m := _member(g, dx)) is not None]

    def ok(c: str) -> bool:
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
            form["pain_site"] = site or ("복부" if chemo else "수술 예정 부위")   # the admission pain has a place
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
    if "fall_history" in form:   # the fall that brought the patient in counts (user 2026-10-17)
        fell = any(w in cc for w in ("낙상", "미끄러", "넘어", "골절"))
        form["fall_history"] = "yes" if fell or (age >= 75 and rng.random() < 0.08) else "no"
    # an elective admission is awake; confusion only in the very old after a fall
    if "consciousness" in form:
        form["consciousness"] = "confuse" if (age >= 75 and any(w in cc for w in ("낙상", "골절", "미끄러")) and rng.random() < 0.15) else "alert"
    if "isolation" in form:
        form["isolation"] = "contact" if rng.random() < 0.05 else "none"
    if "devices" in form and not chemo and not any(w in cc for w in ("장루", "회장루")):
        form.pop("devices")                  # a THA patient does not come in with a stoma or a PICC
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
        # 정서평가 (user 2026-10-17): the 2-week day counts follow whether the patient is worried about the admission
        worried = any(e in (form.get("emotion") or []) for e in ("anxiety", "depression"))
        form["mood_days"] = rng.choices(["none", "few", "week", "daily"], weights=[25, 50, 15, 10])[0] if worried else rng.choices(["none", "few"], weights=[9, 1])[0]
        form["interest_days"] = rng.choices(["none", "few", "week", "daily"], weights=[45, 35, 12, 8])[0] if worried else "none"
        form["depression_screen"] = "pos" if form["mood_days"] in ("week", "daily") or form["interest_days"] in ("week", "daily") else "neg"
        _days = {"none": "없다고", "few": "며칠 있다고", "week": "일주일 넘게 있다고", "daily": "거의 매일 있다고"}
        form["mood_summary"] = f"기분 가라앉은 날이 {_days[form['mood_days']].replace('다고', '고') if form['mood_days'] != 'none' else '없고'} 흥미 떨어진 날은 {_days[form['interest_days']]}"
        if "selfharm" in form and form["depression_screen"] == "neg":
            form["selfharm"] = "none"
    # 금연·금주 교육은 해당 환자에게만 (user 2026-10-17); set unconditionally so the bool never lags the habit field
    form["smoking_edu"] = form.get("smoking") == "current"
    form["alcohol_edu"] = form.get("alcohol") in ("social", "heavy")
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


# ---------------------------------------------------------------------------
# S2 · S3-1 · S3-2 · S4 · S5 · S6: derived from the patient the way S1 is (2026-10-17 audit, ≥10 scripts per template)
# ---------------------------------------------------------------------------

_UPPER_LIMB = ("손목", "요골", "쇄골", "상완골", "어깨", "견관절", "회전근개")


def _upper_limb(dx: str) -> bool:
    return any(w in dx for w in _UPPER_LIMB)


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
    pool = coherent_pool(patient.diagnosis, tuple(pool), trauma=False) or pool
    return _fill(rng.choice(pool), patient, sc) if pool else ""


def _scenario_drains(sc) -> list[str]:
    return [x for x in ((sc.form.get("s3_1.drain") if sc else None) or ["none"]) if x != "none"]


def _drain_text(rng: random.Random, patient: Patient, sc, tkey: str) -> str:
    """'JP serosanguineous 40cc' for a patient whose surgery actually leaves a drain, else ''."""
    if patient.kind == "chemo" or not _scenario_drains(sc):
        return ""
    txt = _pick(rng, patient, sc, "drain", tkey) if (sc.pools.get(f"{tkey}.drain") or sc.pools.get("drain")) else ""
    if txt:
        return txt
    kind = "Hemovac" if patient.department == "정형외과" else "JP"
    color = "sanguineous" if (patient.pod or 0) == 0 else rng.choice(["serosanguineous", "serosanguineous", "serous"])
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
    lateral = any(w in patient.diagnosis for w in _SIDES) or patient.department == "정형외과" or "유방" in patient.diagnosis
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
    form["understanding"] = rng.choices(["both", "patient", "re_edu"], weights=[70, 25, 5])[0]
    form["waiting"] = "absent" if rng.random() < 0.15 else "done"
    abdominal = sc is not None and sc.form.get("abdomen", 1) is not None
    qs = [q for q in TEXT_POOLS["question"] if abdominal or "가스" not in q]
    if rng.random() < 0.7:
        form["question"] = rng.choice(qs)
    else:
        form.pop("question", None)
    if sc is not None and sc.key == "BKA":
        form["ambulation"], form["leg"] = False, False


def _derive_s3_1(form: dict[str, Any], patient: Patient, sc, rng: random.Random) -> None:
    """Immediate post-op record = POD 0, right after the patient comes up from the recovery room (user 2026-10-17:
    "수술 후 기록은 POD#0 수술 나왔을 때 바로 하는 기록"); the next days belong to the progress record (S6)."""
    pod = 0
    patient.pod = pod
    day0 = pod == 0
    form["timing"] = {0: "day0", 1: "pod1", 2: "pod2"}[pod]
    if day0:
        form["arrival_time"] = rng.choice(TEXT_POOLS["arrival_time"])
        form["vs_lead"] = rng.choice(["도착 당시", "병실 도착 후", "도착 직후"])
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
    if sc is not None and sc.key == "Tracheostomy":
        o2 = rng.choice(["mask", "nasal"])
    forced = (sc.form.get("s3_1.o2") or sc.form.get("o2")) if sc else None
    if forced and o2 not in forced:
        o2 = forced[0]
    form["o2"] = o2
    v["o2"] = {"none": "room air", "nasal": rng.choice(["O2 2L nasal", "O2 3L nasal"]), "mask": "O2 5L mask"}[o2]
    if rng.random() < 0.1:
        v["bt"] = round(rng.uniform(37.6, 38.2), 1)   # low-grade post-op fever
    form["vitals"] = v
    form["nrs"] = rng.randint(*{0: (3, 6), 1: (2, 5), 2: (1, 4)}[pod])
    if form.get("pain_med") == "none":
        form["nrs"] = min(form["nrs"], 2)
    if pod >= 2 and minor and form.get("pain_med") in ("pca", "prn_iv"):
        form["pain_med"] = rng.choice(["prn_po", "regular"])     # a 2-day surgery is on tablets by POD 2
    form["pca_edu"] = form.get("pain_med") == "pca" and day0 and form["consciousness"] == "alert"
    form["breathing"] = "intensive" if day0 else "inspirometer"
    if not day0:
        form["hob"] = "30"
    # catheter: out by POD 1 unless this surgery keeps it (RALRP); the special education must agree
    keep_only = sc is not None and set(sc.form.get("foley") or []) == {"keep"}
    if not day0 and form.get("foley") == "keep" and not keep_only:
        form["foley"] = rng.choice(["removed", "none"])
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
    form["foley_edu"] = form.get("foley") == "keep" and rng.random() < 0.9
    if form.get("foley_note") and re.search(r"당겨|소변백|제거 예정|관리", form["foley_note"]):
        form["foley_edu"] = False
    if form.get("foley") != "keep":
        form.pop("foley_note", None)
    # 약물 투여: what actually went in after the operation
    meds = []
    if rng.random() < 0.85:
        meds.append(rng.choice(["예방적 항생제 세파졸린 1g IV", "세파졸린 1g IV", "세프트리악손 2g IV"]))
    if form.get("nausea") in ("nausea", "vomit"):
        meds.append(rng.choice(["온단세트론 4mg IV", "메토클로프라미드 10mg IV"]))
    if patient.department == "정형외과" and not _upper_limb(patient.diagnosis):
        meds.append("에녹사파린 40mg 피하 주사")
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
    elif patient.department == "유방외과" or "mastectomy" in key.lower() or "Breast" in key:
        care = ["compression"]
    else:
        care = ["warming"] if rng.random() < 0.3 else []
    form["postop_care"] = care
    abdominal_open = sc is not None and sc.form.get("abdomen", 1) is not None and sc.los[1] >= 4
    if day0 and abdominal_open and form.get("diet_status") in ("sow", "ld", "gd"):
        form["diet_status"] = "npo"       # nobody drinks on the evening of a colon/uterus operation
    if day0 and form.get("ambulation_plan") == "walk_today":
        form["ambulation_plan"] = rng.choice(["evening_sit", "bedrest"])
    if day0 and sc is not None and sc.key in ("BKA", "ORIF") and not _upper_limb(patient.diagnosis):
        form["ambulation_plan"] = "bedrest"
    if not day0:
        form["ambulation_plan"] = "bedrest" if (sc is not None and sc.key == "BKA") else "walk_today"
    lower = (patient.department in ("정형외과", "비뇨의학과") and not _upper_limb(patient.diagnosis)) or \
            (sc is not None and sc.key in ("C-sec", "Hernioplasty", "Hemorrhoidectomy", "Rectal prolapse OP"))
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
    form["understanding"] = "caregiver" if form["consciousness"] == "drowsy" else rng.choices(["both", "patient", "re_edu"], weights=[70, 25, 5])[0]
    if "drain_amount" in form:
        hi_amt = 150 if patient.department == "정형외과" else 90
        form["drain_amount"] = rng.randint(10, 60) if day0 else rng.randint(20, hi_amt)
    form["exam_care"] = "na"


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
            judgement=["요로 감염 가능성"], tail=["소변 혼탁하고 배뇨 시 불편감 있는 상태"],
            orders=["urine culture 시행 후 acetaminophen 650mg PO", "urine analysis, urine culture 시행 후 acetaminophen 1g IV"],
            med=["{t} acetaminophen 650mg PO", "{t} PRN acetaminophen 1g IV"], nursing=[["hydration"], ["hydration", "tepid"]],
            exam=["urine culture 검체 채취하여 검사실로 보냄"], plan=["배양 결과 확인 예정이며 2시간 후 체온 재측정", "수분 섭취 격려하며 배뇨 양상 관찰"]),
        _ev(vs="fever", complaint=["열감 없다고 하나 얼굴 붉어져 있음", "입이 마르고 기운 없다고 함"], lung=["clear"],
            judgement=["탈수 가능성", "수술 후 흡수열 가능성"], tail=["수술 부위와 호흡음 특이 소견 없고 경구 섭취 적은 상태"],
            orders=["수액 500cc 추가 주입, acetaminophen 650mg PO", "N/S 500cc 추가 후 체온 재측정"],
            med=["{t} acetaminophen 650mg PO", ""], nursing=[["hydration", "tepid"], ["hydration"]], exam=[""],
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
                 tail=["오심 호소하며 구토 1회 있는 상태"], orders=["온단세트론 4mg IV 1회", "메토클로프라미드 10mg IV, PCA 속도 조절"],
                 med=["{t} 온단세트론 4mg IV", "{t} 메토클로프라미드 10mg IV"], nursing=[["position"], ["position", "hydration"]], exam=[""],
                 plan=["항구토제 투여 후 오심 재사정, 지속 시 재노티", "오심 호전 후 식이 진행 예정"])],
    "출혈": [_ev(vs="normal", vs_adj={"hr": (92, 110), "sbp": (96, 118)}, complaint=["드레싱에 피 비친다고 호소함", "드레싱 젖은 느낌 있다고 함"], wound=["bleeding"],
               judgement=["수술 부위 출혈 가능성"], tail=["드레싱 혈액으로 젖어 있는 상태"], orders=["드레싱 교환 및 압박 드레싱, CBC F/U", "압박 드레싱 후 관찰, 트라넥삼산 500mg IV, CBC F/U"],
               med=["", "{t} 트라넥삼산 500mg IV"], nursing=[["compression"], ["compression", "position"]], exam=["CBC 채혈하여 검사실로 보냄", ""],
               plan=["CBC 결과 확인 후 주치의 노티 예정이며 드레싱 상태 1시간마다 관찰", "드레싱 상태 지속 관찰 예정"], recheck=True)],
    "저혈압": [_ev(vs="hypo", complaint=["어지럽다고 호소함", "일어설 때 어지럽고 식은땀 난다고 함"], mental=["alert", "drowsy"], urine=["decreased", "clear"],
                judgement=["체액 부족에 의한 저혈압 가능성", "PCA 관련 저혈압 가능성"], tail=["저혈압 상태"],
                orders=["N/S 500cc 로딩 후 V/S 재확인", "수액 로딩 및 PCA 일시 중단, 30분 후 재측정"], med=["{t} N/S 500cc 빠르게", "{t} N/S 500cc 빠르게"],
                nursing=[["leg_up"], ["leg_up", "blanket"]], exam=[""], plan=["30분 후 혈압 재측정 예정이며 유지 안 되면 재노티", "수액 로딩 후 혈압 추적 관찰"])],
    "호흡곤란": [_ev(vs="normal", vs_adj={"rr": (24, 28), "spo2": (89, 93), "hr": (92, 108)}, complaint=["숨차다고 호소함", "가슴 답답하고 숨 쉬기 힘들다고 함"], lung=["crackle", "decreased", "sputum"],
                 judgement=["무기폐 가능성", "폐 합병증 가능성"], tail=["호흡 곤란 호소하는 상태"], orders=["O2 nasal 3L 적용, chest PA, ABGA", "산소 적용 후 SpO2 추적, chest PA 촬영"],
                 med=["", ""], nursing=[["o2", "breathing", "inspirometer", "position"]], exam=["chest PA 촬영 위해 휠체어로 영상의학과 이송함"],
                 plan=["chest PA 결과 확인 후 노티 예정이며 SpO2 지속 관찰", "산소 유지하며 1시간 간격 SpO2 확인 예정"], o2_after="O2 3L nasal")],
    "배액 이상": [_ev(vs="normal", vs_adj={"hr": (88, 104)}, complaint=["특이 호소 없음", "배액관 쪽 불편감 호소함"],
                  drain_text=["JP 배액 sanguineous 양상으로 2시간 동안 150cc 증가함", "JP 배액 색 짙어지고 양 늘어 120cc 확인됨"],
                  judgement=["배액량 증가로 수술 부위 출혈 가능성"], tail=["배액 양상 sanguineous로 짙어지고 양 늘어난 상태"],
                  orders=["CBC F/U, 배액 양상 1시간마다 관찰", "배액관 milking 후 양상 관찰, CBC F/U"], med=["", ""], nursing=[["milking"]],
                  exam=["CBC 채혈하여 검사실로 보냄"], plan=["1시간 후 배액량 재확인 예정이며 증가 시 재노티"], recheck=True)],
    "섬망": [_ev(vs="normal", complaint=["밤에 소리 지르고 라인 빼려고 함", "장소와 시간 헷갈려 하며 집에 가겠다고 함"], mental=["confuse"],
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
_EVENT_OVERRIDES: dict[tuple[str, str], dict[str, Any]] = {
    ("ESS", "출혈"): dict(complaint=["코피 나서 거즈 자주 교환함", "목 뒤로 피 넘어간다고 함"], wound=None, judgement=["비강 패킹 부위 출혈 가능성"], tail=["비강 출혈 지속되는 상태"],
                        orders=["비강 패킹 보강, 머리 올리고 냉찜질, 출혈 지속 시 재노티"], med=[""], nursing=[["icepack", "position"]], exam=[""], plan=["코피 양 1시간마다 관찰 예정"], recheck=False),
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
    if no_wound and (sc.key, ev) not in _EVENT_OVERRIDES:
        cands = [c for c in cands if not c.get("wound")] or cands      # no wound-infection or bleeding story without a wound
    var = dict(rng.choice(cands))
    var.update(_EVENT_OVERRIDES.get((sc.key if sc else "", ev), {}))
    t0 = rng.choice([6, 7, 9, 10, 11, 13, 14, 15, 16, 18, 19, 20, 21, 22, 23, 1, 3, 5]) * 60 + rng.choice([0, 0, 10, 20, 30, 40, 50])
    t_noti = t0 + rng.randint(5, 15)
    t_med = t_noti + rng.randint(10, 30)
    t_re = t0 + (rng.randint(15, 30) if var.get("quick") else rng.randint(60, 120))
    form["found_time"], form["noti_time"], form["re_time"] = _clock(t0), _clock(t_noti), _clock(t_re)
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
    i = rng.randrange(len(var["orders"]))
    form["orders"] = var["orders"][i]
    meds = var.get("med") or [""]
    med = meds[i] if len(meds) == len(var["orders"]) else rng.choice(meds)   # the drug given is the drug ordered
    if med:
        form["med_given"] = med.format(t=_clock(t_med))
    else:
        form.pop("med_given", None)
    nursing = rng.choice(var.get("nursing") or [[]])
    if nursing:
        form["nursing"] = list(nursing)
    else:
        form.pop("nursing", None)
    exam = rng.choice(var.get("exam") or [""])
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
    if resp == "improved":
        rv = random_vitals(rng, "normal", with_spo2=True)
    else:
        rv = dict(v)
        for k in ("sbp", "dbp", "hr", "rr"):
            rv[k] = int(v[k]) + rng.randint(-4, 4)
        rv["bt"] = round(max(36.0, float(v["bt"]) - (rng.uniform(0, 0.4) if ev == "발열" else rng.uniform(-0.1, 0.1))), 1)
    rv["spo2"] = rv["spo2"] or rng.randint(95, 99)
    rv["o2"] = var.get("o2_after", "room air")
    if var.get("o2_after"):
        rv["spo2"] = rng.randint(95, 98)
    form["re_vitals"] = rv
    form["recheck"] = "no_change" if var.get("recheck") and resp != "worse" else "na"
    form["plan"] = rng.choice(var["plan"])


def _derive_s4(form: dict[str, Any], patient: Patient, sc, rng: random.Random) -> None:
    """Discharge education: home drugs by age, ER criteria by admission kind, outpatient date in the patient's calendar."""
    age = patient.age or 50
    chemo = patient.kind == "chemo"
    form["report_edu"] = "chemo" if chemo else "op"
    form["id_check"] = rng.random() < 0.95
    if age < 50:
        form["home_meds"] = "none" if rng.random() < 0.85 else "continue"
    else:
        form["home_meds"] = rng.choices(["continue", "none", "continue_aspirin_later", "changed"], weights=[50, 30, 0 if chemo else 10, 10])[0]
    form["teachback"] = rng.choices(["both", "patient", "caregiver", "re_edu"], weights=[70, 20, 5, 5])[0]
    m = re.match(r"(\d+)월 (\d+)일", patient.op_date or "")
    if m:
        offset = rng.randint(12, 21)
        if not chemo and patient.pod:
            offset = max(offset, patient.pod + rng.randint(5, 9))   # a 21-day BKA stay still has its clinic after discharge
        visit = datetime(2026, int(m.group(1)), int(m.group(2))) + timedelta(days=offset)
        form["opd"] = f"{visit.month}월 {visit.day}일 {rng.choice(['오전 9시', '오전 10시 30분', '오전 11시', '오후 2시', '오후 3시'])}"
        if chemo:                                            # 다음 입원 일자: the cycle after the clinic check (user 2026-10-17)
            nxt = visit + timedelta(days=1)
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
    if _upper_limb(patient.diagnosis) and form.get("activity") == "weight_bearing":
        form["activity"] = "walk_no_heavy"   # a wrist fracture walks normally
    if form.get("device") == "stoma":
        form["referral"] = [r for r in form.get("referral", []) if r != "stoma"]
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
        if any(w in form["activity_note"] for w in ("운전", "복직")):
            form.pop("driving", None)
    if form.get("device_note"):
        form.pop("device", None)
    if re.search(r"38도|발열|고열|열 나|열,|열 지속", form.get("report_note", "")):
        form.pop("report_edu", None)                          # the leaflet warning already lists the fever criterion
    if re.search(r"조직검사|항암 여부|방사선|병리", form.get("opd_note", "")):
        form.pop("further", None)


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
    form["caregiver"] = rng.choices(["spouse", "child", "caregiver", "none", "intermittent"],
                                    weights=[40, 15, 5, 30, 10] if age < 65 else [30, 30, 15, 10, 15])[0]
    form["consciousness"] = "drowsy" if pod == 0 and not chemo and rng.random() < 0.1 else "alert"
    vs = rng.choices(["stable", "fever_resolved", "fever", "hypotension", "tachy"], weights=[75, 10, 5, 2, 8] if chemo else [60, 20, 5, 5, 10])[0]
    form["vs_summary"] = vs
    form["bt_peak"] = round(rng.uniform(37.8, 39.0), 1)
    form["bt_now"] = round(rng.uniform(38.0, 38.9), 1) if vs == "fever" else round(rng.uniform(36.4, 37.4), 1)
    form["sbp"], form["dbp"], form["hr"] = rng.randint(82, 98), rng.randint(45, 60), rng.randint(102, 125)
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
        minor = hi <= 3
        stage = (("sow", "ld") if pod == 0 else ("sd", "gd")) if minor else \
            {0: ("npo",), 1: ("npo", "sow"), 2: ("sow", "ld"), 3: ("ld", "sd")}.get(pod, ("sd", "gd"))
        allowed = [x for x in (sc.form.get("s5.diet") or sc.form.get("diet") or []) if x in stage]
        form["diet"] = rng.choice(allowed) if allowed else stage[-1]
    d = form.get("diet")
    if "gas_out" in form:
        if d == "npo":
            form["gas_out"] = False
        elif d == "sow":
            form["gas_out"] = True        # "가스 아웃 확인되어 물 시작"
        else:
            form.pop("gas_out")       # already past water: nobody announces gas
    had_foley = sc is not None and "keep" in (sc.form.get("foley") or [])
    if not chemo and pod == 0 and had_foley:
        form["voiding"] = "foley"
    elif form.get("voiding") == "foley_removed" and (pod == 0 or pod > 2 or not had_foley):
        form["voiding"] = "self"          # "소변줄 어제 제거" only on POD 1-2 of a surgery that had one
    if pod <= 1 and not chemo:
        form["bowel"] = "diarrhea" if rng.random() < 0.05 else "none_yet"
    else:
        form["bowel"] = rng.choices(["done", "none_yet", "diarrhea"], weights=[7, 2, 1] if chemo else [6, 3, 1])[0]
    form["sleep"] = rng.choices(["good", "poor", "hypnotic"], weights=[70, 20 if form["nrs"] >= 3 else 0, 10 if age >= 65 else 3])[0]   # "통증으로 수면 불량" needs pain
    drain = _drain_text(rng, patient, sc, "s5") if pod <= 4 or rng.random() < 0.5 else ""
    if drain:
        form["drain"] = drain
    else:
        form.pop("drain", None)
    io = f"수액 {rng.randrange(1200, 2200, 100)}, 소변 {rng.randrange(1200, 2400, 100)}"
    if ("JP" in drain or "Hemovac" in drain) and "제거" not in drain:
        io += f", {'Hemovac' if 'Hemovac' in drain else 'JP'} {rng.randrange(20, 120, 10)}"
    if chemo or d in ("sd", "gd", "soft", "dm"):
        io = f"경구 {rng.randrange(800, 1800, 100)} " + io
    form["io"] = io
    if chemo or pod >= 5 or (pod >= 3 and rng.random() < 0.7) or "없음" in form.get("antibiotic", ""):
        form.pop("antibiotic", None)
    elif "antibiotic" in form and not abdominal:
        form["antibiotic"] = "세파졸린 q8h"   # 메트로니다졸 is for bowel surgery
    if chemo:
        prn = ["항구토제 1회"] if rng.random() < 0.4 else []
    elif pod <= 1:
        prn = rng.choice([["트라마돌 1회"], ["항구토제 1회"], ["트라마돌 1회, 항구토제 1회"], []])
    else:
        prn = ["트라마돌 1회"] if rng.random() < 0.3 else []
    if prn:
        form["prn"] = prn[0]
    else:
        form.pop("prn", None)
    form["o2"] = rng.choice(["nasal", "weaning"]) if pod == 0 and not chemo and rng.random() < 0.4 else "none"
    if sc is not None and sc.key == "Tracheostomy":
        form["o2"] = "nasal"
    if not chemo and hi >= 7 and pod <= 2 and rng.random() < 0.2:
        form["transfusion"] = "PRBC 1 pack 수혈 완료"
    else:
        form.pop("transfusion", None)
    sp = [x for x in _pool(sc, "special", "s5") if "퇴원" not in x or chemo or pod >= lo - 1]
    if pod == 0 and not chemo:
        sp = [x for x in sp if not any(w in x for w in ("보행", "어제", "제거"))]
    sp = [x for x in sp if ("미음" not in x or d == "ld") and ("죽식 진행 여부" not in x or d == "ld") and ("제거" not in x or "제거" not in drain)]
    sp = coherent_pool(patient.diagnosis, tuple(sp), trauma=False) or sp
    if sp and rng.random() < 0.8:
        form["special"] = _fill(rng.choice(sp), patient, sc)
    else:
        form.pop("special", None)
    if not chemo:
        site = rng.choice(["Rt arm", "Lt arm", "Rt hand", "Lt forearm", "Lt hand", "오른팔", "왼팔"])
        gauge = rng.choice(["20G", "22G", "22G", "24G"])
        when = rng.choice([f"{patient.admission_date} 삽입", "오늘 교환함", f"{patient.op_date} 삽입"]) if pod <= 2 else rng.choice(["오늘 교환함", "어제 교환함", "내일 교환 예정"])
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
    near_dc = chemo or pod >= lo - 1
    pump = "FOLF" in (patient.regimen or "")
    pend = [x for x in _pool(sc, "pending", "s5") if ("미음" not in x or d in ("npo", "sow")) and ("퇴원" not in x or near_dc) and ("펌프" not in x or pump)]
    if pend:
        form["pending"] = _fill(rng.choice(pend), patient, sc)
    else:
        form.pop("pending", None)
    plans = [x for x in _pool(sc, "plan", "s5") if "수술 준비" not in x and ("PICC" not in x or "PICC" in form.get("line", ""))
             and ("퇴원" not in x or near_dc) and ("폐활량계" not in x or pod <= 2) and ("펌프" not in x or pump)]
    if "퇴원" in form.get("special", "") and not chemo:
        plans = ["퇴원 교육 시행", "퇴원 처방 확인"]
    if plans:
        form["plan"] = _fill(rng.choice(plans), patient, sc)
    else:
        form.pop("plan", None)


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
    form["nrs1"] = rng.choice([0, 0, 1, 2]) if chemo else rng.randint(*{"slept": (1, 3), "pain_wake": (4, 7), "restless": (2, 5)}.get(night, (1, 3)))
    pca_ok = not chemo and pod <= 2 and sc is not None and any("pca" in x for x in (sc.form.get("pain_mgmt") or []))
    if chemo:
        form["pain_plan"] = "prn" if form["nrs1"] >= 4 else "explain"
    elif form["nrs1"] >= 5:
        form["pain_plan"] = "pca" if pca_ok and rng.random() < 0.5 else "prn"
    else:
        form["pain_plan"] = "pca" if pca_ok and rng.random() < 0.5 else rng.choice(["explain", "explain", "prn"])
    form["pca_remove"] = ("removed" if pod >= 1 and rng.random() < 0.6 else "keep") if form["pain_plan"] == "pca" else "na"
    form["reassess"] = "after_pca" if form["pca_remove"] == "removed" else "after_prn" if form["pain_plan"] == "prn" else "stable"
    form["nrs4"] = max(0, form["nrs1"] - rng.randint(2, 4)) if form["reassess"] != "stable" else min(form["nrs1"], rng.randint(0, 3))
    if form["nrs1"] == 0:
        form.pop("pain_desc", None)       # no "어디가 아프다" at NRS 0
    form["vitals"] = random_vitals(rng, "normal", with_spo2=True)   # the 7 o'clock round of a stable patient
    abdominal = not chemo and sc is not None and sc.form.get("abdomen", 1) is not None
    form["meal1"] = "npo" if abdominal and pod <= 1 and rng.random() < 0.5 else rng.choices(["all", "half", "little"], weights=[6, 3, 1])[0]
    form["meal2"] = "npo" if form["meal1"] == "npo" else rng.choices(["all", "half"], weights=[7, 3])[0]
    if pod >= 1 or chemo:
        form["vitals"]["o2"] = "room air"
    form["fall"] = rng.random() < 0.8
    # --- afternoon / evening entries (user 2026-10-17: 그날 있었던 기록을 시간대별로) ---
    if chemo:
        form["afternoon_activity"] = "chemo_infusion"
    elif sc is not None and sc.key == "BKA":
        form["afternoon_activity"] = "bedrest" if pod <= 1 else "walk_assist"
    else:
        form["afternoon_activity"] = "sit" if pod == 0 else ("walk_assist" if pod == 1 else rng.choice(["walk_assist", "walk_self"]))
    if not chemo and _scenario_drains(sc) and pod <= 3:
        form["drain_note"] = f"{'Hemovac' if patient.department == '정형외과' else 'JP'} 배액 {rng.choice(['serosanguineous', 'serous'])} {rng.randint(10, 80)}cc 비우고 양상 관찰함"
    elif not chemo and pod <= 1 and sc is not None and "keep" in (sc.form.get("foley") or []):
        form["drain_note"] = "소변줄 통해 소변 맑고 시간당 50cc 이상 나옴"
    elif rng.random() < 0.5:
        form["drain_note"] = rng.choice(["자가배뇨 양호함", "배뇨 불편감 없음"])
    else:
        form.pop("drain_note", None)
    form["vitals_evening"] = random_vitals(rng, "normal", with_spo2=False)
    form["evening_note"] = rng.choices(["stable", "visit", "edu", "pain_prn"], weights=[55, 20, 15, 10])[0]
    if form["evening_note"] == "pain_prn" and form["pain_plan"] == "pca" and form["pca_remove"] == "keep":
        form["evening_note"] = "stable"               # a running PCA is not topped up with PRN
    # Evening/Night (user 2026-10-17: 세 듀티의 정규 라운딩 + 이벤트); the clock keeps the three roundings at 07:xx, 15:xx, 23:xx
    form["t1"] = rng.choice(["오전 7시", "오전 7시 10분", "오전 7시 30분"])
    form["t2"] = rng.choice(["오전 8시", "오전 8시 10분"])
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
    form["night_onset"] = rng.choices(["asleep", "resting", "awake_pain", "hypnotic"], weights=[60, 25, 10 if form["nrs_n"] >= 3 else 0, 8 if age >= 65 else 2])[0]
    if form["night_onset"] == "awake_pain":
        form["nrs_n"] = max(form["nrs_n"], 4)
    form["night_line"] = rng.random() < 0.85
    # --- charting checklist: only protocols this patient can have, with details taken from the record ---
    hi_fall = age >= 70 or (patient.department == "정형외과" and age >= 60) or any(w in patient.diagnosis for w in _TRAUMA) \
        or (sc is not None and sc.key in ("THA", "TKA", "BKA"))
    if not hi_fall:
        _drop_section(form, t, "prot_fall_high")
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
    foley_ok = not chemo and sc is not None and "keep" in (sc.form.get("foley") or []) and pod <= 1
    if not foley_ok:
        _drop_section(form, t, "prot_foley")
    elif _section_on(form, t, "prot_foley"):
        form["p_foley_date"] = patient.op_date
        if form.get("p_self_void") or form.get("p_residual_check"):
            form["p_foley_remove"] = True
    if form["pain_plan"] != "pca":
        for k in [k for k in form if k.startswith("p_pca_")]:
            form.pop(k)
    else:
        form.pop("p_pca_end", None)          # e3 already says whether the PCA came out
    if form["nrs1"] < 4 and form["pain_plan"] != "prn":
        _drop_section(form, t, "prot_apain")   # nobody medicates a 2-point pain
    elif _section_on(form, t, "prot_apain"):
        form["p_apain_score"] = max(form["nrs1"], 4)
        form["p_apain_re_score"] = min(form["nrs4"], form["p_apain_score"] - 2)
    if chemo:
        _drop_section(form, t, "prot_breath")
    if form.get("p_diet_adjust"):
        form["meal2"] = "npo"                # vomiting at lunch
    if pod >= 1 or chemo:
        form.pop("p_ast", None)              # the skin test was done before the first dose
    if _section_on(form, t, "prot_glucose"):
        form["p_bst"] = True                 # insulin only after a measured value
    if (pod >= 1 or chemo) and not (sc is not None and sc.key == "Tracheostomy"):
        form.pop("p_o2_apply", None)
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
        form["p_wound_state"] = rng.choices(["clean", "dry", "red", "ooze"], weights=[6, 3, 1, 1])[0]
    form["p_apain_scale"] = form["p_cpain_scale"] = "NRS"
    form["p_iv_patency"] = "양호함" if rng.random() < 0.9 else form.get("p_iv_patency", "양호함")
    if chemo:
        form["p_med_name"] = rng.choice(["온단세트론 8mg", "덱사메타손 10mg", "아프레피탄트 125mg"])
        form.pop("p_ast", None)
    form["p_meal_note"] = {"npo": "npo", "all": "all", "half": "half", "little": "little"}[form["meal1"]]
    if rng.random() < 0.8:
        form["p_status_note"] = "stable"
    if _section_on(form, t, "prot_fever"):
        form["bt3"] = form.get("p_temp", form.get("bt3"))
    else:
        form["bt3"] = round(rng.uniform(36.3, 37.4), 1)
    # dinner follows the final lunch state (the 오심 protocol may have made lunch 금식 above)
    form["meal3"] = "npo" if form["meal2"] == "npo" else rng.choices(["all", "half"], weights=[7, 3])[0]

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
        pool = coherent_pool(patient.diagnosis, tuple(pool), trauma=False) or list(pool)
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
                pool = coherent_pool(patient.diagnosis, tuple(pool), trauma=False) or list(pool)   # 좌측 손목 골절 ↔ "발목 올리기" 금지
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
