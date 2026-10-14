"""Virtual patient and random form generation for bulk recording."""
from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any

from .generator import Patient
from .templates import get_template
from .templates.base import Field

SURNAMES = ["김", "이", "박", "최", "정", "강", "조", "윤", "장", "임", "한", "오", "서", "신", "권", "황", "안", "송", "류", "홍",
            "전", "고", "문", "손", "양", "배", "백", "허", "유", "남", "심", "노", "하", "곽", "성", "차", "주", "우", "구", "민"]
GIVEN_M = ["민수", "영호", "철수", "성민", "준호", "동현", "재현", "정훈", "상우", "병철", "기훈", "태영", "현우", "진우", "영식",
           "종수", "만수", "경수", "대성", "성호", "우진", "지훈", "도현", "승현", "병호", "창수", "광수", "덕수", "길동", "석진"]
GIVEN_F = ["영희", "미경", "지영", "수진", "은정", "현주", "미숙", "정희", "순자", "혜진", "지은", "민정", "선영", "경희", "미영",
           "영숙", "옥순", "말순", "정순", "혜경", "수연", "유진", "소연", "다혜", "보람", "하늘", "은주", "숙자", "명희", "춘자"]

PROFESSORS = ["김민수", "이정호", "박상현", "최유진", "정우성", "강동원", "한지민", "윤석우", "장현식", "임채영", "오세훈", "서지혜"]

# (diagnosis, surgery, department, typical age range, sex bias)
CASES = [
    ("위암", "Laparoscopic total gastrectomy", "외과", (45, 80), None),
    ("위암", "Laparoscopic subtotal gastrectomy", "외과", (45, 80), None),
    ("위암", "Laparoscopic distal gastrectomy", "외과", (40, 78), None),
    ("대장암", "Laparoscopic right hemicolectomy", "외과", (50, 82), None),
    ("직장암", "Laparoscopic low anterior resection", "외과", (45, 80), None),
    ("S상결장암", "Laparoscopic anterior resection", "외과", (45, 80), None),
    ("담석증", "Laparoscopic cholecystectomy", "외과", (30, 75), None),
    ("급성 충수염", "Laparoscopic appendectomy", "외과", (18, 60), None),
    ("유방암", "Mastectomy", "외과", (35, 70), "여"),
    ("폐암", "Lobectomy", "흉부외과", (50, 78), None),
    ("무릎 골관절염", "Total knee replacement arthroplasty", "정형외과", (60, 82), "여"),
    ("대퇴골 경부 골절", "Total hip replacement arthroplasty", "정형외과", (65, 90), None),
    ("자궁근종", "Hysterectomy", "산부인과", (38, 60), "여"),
    ("췌장암", "PPPD", "외과", (50, 75), None),
    ("간세포암", "Hepatectomy", "외과", (45, 75), "남"),
    ("갑상선암", "Thyroidectomy", "외과", (25, 65), "여"),
]

TEXT_POOLS: dict[str, list[str]] = {
    "chief_complaint": ["2개월 전부터 상복부 불편감, 체중 5kg 감소", "건강검진에서 우연히 발견된 종괴", "3주 전부터 간헐적 복통", "혈변 2회",
                        "우상복부 통증과 소화불량", "1개월 전부터 식후 더부룩함", "무릎 통증으로 보행 어려움", "낙상 후 우측 고관절 통증"],
    "onset": ["2개월 전부터", "3주 전부터", "1개월 전", "어제 저녁부터", "6개월 전부터 서서히"],
    "present_illness": ["8월 건강검진 위내시경에서 종괴 발견되어 조직검사상 선암 진단", "타병원 대장내시경에서 종괴 발견, 조직검사상 선암",
                        "외래 CT에서 담낭 결석 및 담낭염 소견", "응급실 CT에서 급성 충수염 진단", "유방 초음파 및 조직검사상 침윤성 유방암"],
    "s1.plan": ["복강경 수술 예정", "수술 후 조직검사 결과에 따라 추가 치료 결정 예정", "수술 예정"],
    "history_detail": ["고혈압 10년, 당뇨 5년 경구약 복용", "고혈압 5년 약 복용 중", "당뇨 8년 인슐린 사용", "특이사항 없음", "협심증으로 스텐트 시술 3년 전"],
    "past_surgery": ["20년 전 충수절제술", "10년 전 제왕절개", "없음", "5년 전 담낭절제술", "2년 전 백내장 수술"],
    "allergy_reaction": ["두드러기", "가려움", "호흡곤란", "발진"],
    "medications": ["암로디핀 5mg, 메트포르민 500mg bid", "로사르탄 50mg qd", "메트포르민 500mg bid, 아토르바스타틴 20mg", "없음",
                    "아스피린 100mg, 클로피도그렐 75mg", "레보티록신 50mcg qd"],
    "supplements": ["오메가3", "홍삼", "비타민 D", "없음"],
    "family_history": ["부친 위암", "모친 당뇨", "없음", "형제 대장암", "부친 고혈압"],
    "weight_change": ["2개월간 5kg 감소", "변화 없음", "1개월간 3kg 감소"],
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
    "vs_lead": ["도착 당시", "병실 도착 후 측정한", "오후 2시"],
    "iv": ["좌측 전완 말초 라인 통해 H/S, DW 수액", "우측 손등 말초 라인 통해 하트만 수액", "우측 전완 말초 라인 통해 N/S 수액", "PICC 통해 TPN"],
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
    "discharge_date": ["내일 오전", "오늘 오후", "모레 오전", "내일 10월 18일 오전"],
    "course": ["수술 후 특이 합병증 없이 회복", "수술 후 발열 있었으나 호전", "수술 후 장폐색 없이 식이 진행 양호"],
    "discharge_meds": ["아세트아미노펜 650mg 하루 세 번 식후 5일분, 위장운동촉진제 하루 세 번 식전 2주분, 철분제 하루 한 번",
                       "아세트아미노펜 650mg 하루 세 번 3일분, 세파클러 하루 세 번 5일분", "진통제 5일분과 변비약 2주분"],
    "driving": ["운전은 2주 후, 복직은 외래 확인 후", "운전은 1주 후 가능", "복직은 4주 후"],
    "opd": ["10월 27일 오전 10시 30분", "10월 30일 오후 2시", "11월 3일 오전 9시"],
    "opd_exam": ["당일 8시 30분 채혈", "외래 전 CT 예정", "검사 없음"],
    "allergy": ["조영제", "페니실린", "NSAIDs", "없음", "새우"],
    "io": ["수액 2000, 소변 1800, JP 60", "수액 1800, 소변 1500, JP 40", "경구 1200 수액 1500, 소변 2100"],
    "fluid": ["하트만 80cc/hr", "N/S 60cc/hr", "5DW 40cc/hr", "하트만 100cc/hr"],
    "antibiotic": ["세파졸린 q8h", "세프트리악손 q24h", "항생제 없음", "메트로니다졸 q8h 추가"],
    "prn": ["트라마돌 1회", "항구토제 1회", "없음", "트라마돌 2회, 수면제 1회"],
    "transfusion": ["", "PRBC 1 pack 수혈 완료", "", ""],
    "line": ["오른팔 말초 라인 하나, 10월 13일 삽입이라 내일 교환 예정", "왼팔 말초 라인 하나, 오늘 교환함", "PICC 우측 상완, 주 1회 드레싱"],
    "other_tube": ["", "", "L-tube 자연 배액 중", ""],
    "lab": ["WBC 11.2, CRP 8.5로 어제보다 약간 상승", "Hb 9.8로 감소", "K 3.2로 낮아 KCl 추가", "특이 소견 없음"],
    "glucose": ["식전 150~180으로 슬라이딩 스케일", "식전 120~140, 인슐린 없음", "식전 200 이상으로 RI 4단위 추가"],
    "imaging": ["chest PA 특이 소견 없음", "복부 CT 결과 확인 예정", ""],
    "pending": ["내일 아침 랩 결과 확인 후 미음 진행 여부 담당의 확인", "협진 회신 확인", "보호자 면담 요청 있어 주치의 확인 필요", "퇴원 처방 확인"],
}

# Diagnosis-specific complaints so a virtual patient's story hangs together.
DX_DETAILS: dict[str, dict[str, list[str]]] = {
    "위암": {"cc": ["2개월 전부터 상복부 불편감, 체중 5kg 감소", "식후 더부룩함과 소화불량", "건강검진에서 우연히 발견된 위 종괴", "흑색변 2회"],
             "pi": ["8월 건강검진 위내시경에서 종괴 발견되어 조직검사상 선암 진단", "타병원 위내시경에서 위체부 종괴 발견, 조직검사상 선암", "상복부 불편감으로 시행한 위내시경에서 조기위암 진단"]},
    "대장암": {"cc": ["혈변 2회", "3주 전부터 간헐적 복통과 변비", "건강검진 대장내시경에서 종괴 발견", "체중 감소와 빈혈"],
              "pi": ["타병원 대장내시경에서 종괴 발견, 조직검사상 선암", "건강검진 대장내시경에서 상행결장 종괴 발견되어 조직검사상 선암 진단"]},
    "직장암": {"cc": ["혈변과 배변 습관 변화", "잔변감과 가는 변", "항문 출혈 1개월"],
              "pi": ["대장내시경에서 직장 종괴 발견, 조직검사상 선암", "직장 선암으로 선행 항암방사선치료 후 수술 예정"]},
    "S상결장암": {"cc": ["좌하복부 통증과 변비", "혈변 1회"], "pi": ["대장내시경에서 S상결장 종괴 발견, 조직검사상 선암"]},
    "담석증": {"cc": ["우상복부 통증과 소화불량", "식후 우상복부 통증 반복", "오한 동반한 우상복부 통증"],
              "pi": ["외래 CT에서 담낭 결석 및 담낭염 소견", "응급실 초음파에서 담낭 결석과 담낭벽 비후 소견"]},
    "급성 충수염": {"cc": ["어제 저녁부터 우하복부 통증", "복통과 오심, 미열", "배꼽 주위 통증이 우하복부로 이동"],
                 "pi": ["응급실 CT에서 급성 충수염 진단", "응급실 CT에서 충수 비후 및 주위 염증 소견"]},
    "유방암": {"cc": ["우측 유방 종괴 촉지", "검진 유방촬영에서 이상 소견", "좌측 유방 멍울과 통증"],
              "pi": ["유방 초음파 및 조직검사상 침윤성 유방암", "선행 항암 후 수술 예정"]},
    "폐암": {"cc": ["1개월 전부터 마른기침", "검진 CT에서 폐 결절 발견", "객혈 1회"],
            "pi": ["흉부 CT에서 우상엽 결절 발견, 조직검사상 선암", "PET-CT상 원격 전이 없어 수술 예정"]},
    "무릎 골관절염": {"cc": ["무릎 통증으로 보행 어려움", "수년간 지속된 양측 무릎 통증", "계단 오르내리기 어려움"],
                  "pi": ["엑스레이상 말기 골관절염으로 인공관절 치환술 예정", "보존적 치료에 반응 없어 수술 예정"]},
    "대퇴골 경부 골절": {"cc": ["낙상 후 우측 고관절 통증", "미끄러진 후 좌측 고관절 통증과 보행 불가"],
                    "pi": ["응급실 엑스레이상 대퇴골 경부 골절 진단", "낙상 후 골절로 입원"]},
    "자궁근종": {"cc": ["생리 과다와 빈혈", "하복부 압박감", "생리통 심해짐"],
               "pi": ["초음파에서 8cm 크기 자궁근종 확인", "약물 치료에 반응 없어 수술 예정"]},
    "췌장암": {"cc": ["황달과 체중 감소", "상복부 통증과 식욕 저하", "소변 색 진해짐"],
              "pi": ["CT에서 췌두부 종괴 발견, ERCP 조직검사상 선암", "폐쇄성 황달로 ENBD 시행 후 수술 예정"]},
    "간세포암": {"cc": ["검진 초음파에서 간 종괴 발견", "우상복부 불편감", "B형 간염 추적 중 발견된 종괴"],
               "pi": ["간 MRI에서 간세포암 소견, 수술 예정", "B형 간염 보유자로 추적 중 간 종괴 발견"]},
    "갑상선암": {"cc": ["검진 초음파에서 갑상선 결절 발견", "목 앞쪽 멍울", "특이 증상 없이 검진에서 발견"],
               "pi": ["갑상선 세침검사상 유두암 진단", "초음파 및 세침검사상 갑상선 유두암"]},
}

VS_PROFILE = {
    "normal": {"sbp": (105, 140), "dbp": (60, 88), "hr": (62, 92), "rr": (16, 20), "bt": (36.2, 37.1), "spo2": (96, 99)},
    "fever": {"sbp": (120, 155), "dbp": (70, 92), "hr": (88, 110), "rr": (18, 24), "bt": (37.8, 38.9), "spo2": (94, 98)},
    "hypo": {"sbp": (82, 98), "dbp": (45, 60), "hr": (95, 120), "rr": (18, 24), "bt": (36.0, 36.8), "spo2": (93, 97)},
}


def random_patient(rng: random.Random, template_key: str | None = None) -> Patient:
    dx, surg, dept, (a0, a1), sex_bias = rng.choice(CASES)
    sex = sex_bias or rng.choice(["남", "여"])
    name = rng.choice(SURNAMES) + rng.choice(GIVEN_M if sex == "남" else GIVEN_F)
    age = rng.randint(a0, a1)
    pod = {"s1": None, "s2": None, "s3_1": rng.choice([0, 1, 2]), "s3_2": rng.choice([1, 2, 3]),
           "s4": rng.choice([4, 5, 6, 7]), "s5": rng.choice([1, 2, 3, 4])}.get(template_key or "", rng.choice([1, 2, 3]))
    base_day = rng.randint(1, 28)
    month = rng.randint(1, 12)
    return Patient(name=name, age=age, sex=sex, diagnosis=dx, surgery=surg, professor=rng.choice(PROFESSORS),
                   department=dept, pod=pod, op_date=f"{month}월 {base_day}일", admission_date=f"{month}월 {max(1, base_day - 1)}일")


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
    ranges = {"nrs": (0, 7), "braden": (14, 23), "morse": (0, 65), "height": (148, 182), "weight": (42, 95),
              "bmi": (17.5, 31.0), "drain_amount": (5, 120), "bt_peak": (37.3, 38.9), "bt_now": (36.4, 37.6),
              "sbp": (80, 100), "dbp": (45, 62), "hr": (100, 125)}
    lo, hi = ranges.get(key, (f.min or 0, f.max or 10))
    if f.step and f.step < 1 or isinstance(lo, float):
        return round(rng.uniform(float(lo), float(hi)), 1)
    v = rng.randint(int(lo), int(hi))
    if key == "morse":
        v = (v // 5) * 5
    return v


def random_form(template_key: str, rng: random.Random, patient: Patient | None = None) -> dict[str, Any]:
    t = get_template(template_key)
    form: dict[str, Any] = {}
    for _, f in t.iter_fields():
        if f.kind == "select":
            if f.default is not None and rng.random() < 0.3:
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
            form[f.key] = rng.random() < 0.8 if f.default else rng.random() < 0.3
        elif f.kind == "text":
            pool = TEXT_POOLS.get(f"{template_key}.{f.key}", TEXT_POOLS.get(f.key))
            if pool:
                val = rng.choice(pool)
                if val and val not in ("없음", "허용 약 없음", "특이 질문 없음", "검사 없음", "배액관 없음", "특이사항 없음", "항생제 없음"):
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
    # keep things consistent
    if patient is not None and patient.diagnosis in DX_DETAILS:
        d = DX_DETAILS[patient.diagnosis]
        if "chief_complaint" in form:
            form["chief_complaint"] = rng.choice(d["cc"])
        if "present_illness" in form:
            form["present_illness"] = rng.choice(d["pi"])
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
