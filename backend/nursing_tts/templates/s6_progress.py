"""S6. 경과기록 — 세 듀티(Day 07:00 · Evening 15:00 · Night 23:00)의 정규 첫 라운딩 사정을 모두 차팅하고, 그 사이는 식이 확인 같은
이벤트 차팅 (user 2026-10-17). 수술 환자가 아닌 입원 환자도 쓴다. 정규 차팅 체크리스트(프로토콜)는 Day 아침 식사 뒤 시각 순서로 끼어든다.
수술 당일 병실 도착 직후는 S3-1 수술 후 기록."""
from .base import Field, RecordTemplate, Section, opt, sel, multi, num, txt, boolean
from .common import VITALS_FIELD

_T = lambda key, default: txt(key, "시각", placeholder=f"예: {default}", phrases=["{v} 환자명 {name}.", "{v}, 환자명 {name}.", "{v} {name} 님."], default=default)

TEMPLATE = RecordTemplate(
    key="s6",
    title="S6. 경과기록 (기록체, 하루 세 듀티)",
    signal_kind="경과기록",
    description="하루 동안의 간호기록을 시각 순서로 차팅하듯 구술합니다. Day(07:00)·Evening(15:00)·Night(23:00) 정규 첫 라운딩에서 사정한 내용을 모두 말하고, 그 사이는 식사 확인·PCA·재사정·저녁 이벤트 같은 이벤트 차팅입니다. '~함/~됨' 기록체가 기본이며, 시각마다 '환자명 ○○○'을 다시 말합니다. 수술 당일 병실 도착 직후는 S3-1.",
    intros=["지금 경과기록 하겠습니다.", "{name} 님 오늘 경과기록 하겠습니다.", "{name} 님 경과기록 시작합니다.", "환자명 {name}, 경과기록 하겠습니다."],
    closings=["이상 경과기록 마치겠습니다.", "이상 경과기록 마치겠습니다.", "이상 {name} 님 경과기록 마치겠습니다.", "여기까지 {name} 님 경과기록입니다."],
    sections=[
        Section("d_round", "Day 라운딩 (07:00) — 정규 사정", hint="밤 동안 수면, 통증, 낙상 예방, 수액·라인, 상처, V/S", fields=[
            _T("t1", "오전 7시"),
            sel("night", "밤 동안", [
                opt("slept", "잘 잤음", "환자 밤 동안 특이사항 없이 잘 잤다고 함.", "밤새 특이사항 없이 수면 취함.", "밤 동안 잘 주무셨다고 함."),
                opt("pain_wake", "통증으로 깸", "밤 동안 통증으로 두세 번 깼다고 함.", "통증 때문에 수면 불량했다고 함."),
                opt("restless", "뒤척임", "밤 동안 뒤척이며 깊게 못 잤다고 함.", "새벽에 잠들기 어려웠다고 함."),
            ], default="slept"),
            txt("pain_desc", "통증 호소", placeholder="예: 수술 부위 복부 쪽 쑤시는 느낌",
                phrases=["{v}으로 아프다고 하고,", "{v}으로 통증 호소함.", "{v}으로 아프다고 표현함."], default="수술 부위 복부 쪽 쑤시는 느낌"),
            num("nrs1", "NRS", min=0, max=10, default=3, phrases=["NRS {v}점으로 사정됨.", "통증 {v}점.", "통증 점수 {v}점 측정됨."]),
            sel("pain_plan", "통증 중재", [
                opt("explain", "추가 중재 원치 않음, 진통제 요구 교육", "추가적인 중재 원하지 않음. 통증 심해지기 전에 진통제 요구할 것 설명함.",
                    "추가 중재 원하지 않아 통증 심해지면 미리 알리도록 교육함."),
                opt("prn", "PRN 투여", "PRN 진통제 투여함.", "PRN 트라마돌 IV 투여하고 30분 뒤 재사정 예정."),
                opt("pca", "PCA 유지", "PCA 유지 중이며 버튼 사용 잘 함.", "PCA로 조절 중임."),
            ], default="explain"),
            boolean("fall", "낙상 예방 확인", phrases=["낙상 예방 위해서 침대 높이 낮추고 사이드레일 올려주고 바퀴 고정되어 있는지 확인함.",
                    "침상 낮추고 난간 올리고 바퀴 고정 확인함.", "낙상 예방 활동 시행함."], default=True),
            txt("fluid", "수액", placeholder="예: 하트만 덱스 주사액 1리터 컨트롤 세트로 40cc per hour",
                phrases=["현재 {v} 들어가고 있고,", "{v} 주입 중이고,", "수액 {v} 유지 중."], default="하트만 덱스 주사액 1리터 컨트롤 세트로 40cc/hr"),
            txt("line", "라인", placeholder="예: Lt arm 22G, 왼팔 22게이지",
                phrases=["{v}로 정맥 잘 주입되고 있음. 혈액 역류 잘 확인됨.", "{v} 라인 개방성 확인됨.", "{v} 통해 수액 잘 들어감. 역류 확인됨."], default="왼팔 22게이지"),
            txt("wound", "상처", placeholder="예: 복부 단일공, 소독 잘 되어 있음",
                phrases=["{v} 소독 잘 되어 있으며 상처 치유 상태 문제 없고 건조함.", "{v} 드레싱 깨끗하고 건조함.",
                         "{v} 상처 발적, 삼출물 없음."], default="복부 단일공 수술 부위"),
            VITALS_FIELD,
        ]),
        Section("d_morning", "아침 식사 (08:00) — 이벤트", fields=[
            _T("t2", "오전 8시"),
            sel("meal1", "식사", [
                opt("all", "전량 섭취", "일반식 상식 전량 섭취함.", "아침 식사 전량 드심.", "식사 전량 섭취함."),
                opt("half", "절반", "일반식 절반 정도 섭취함.", "아침 반 정도 드심."),
                opt("little", "소량", "식사 소량만 섭취함. 식욕 저하 호소.", "아침 거의 못 드심."),
                opt("npo", "금식", "금식 유지 중.", "NPO 유지함."),
            ], default="all"),
        ]),
        Section("d_noon", "점심·중재 (12:30) — 이벤트", fields=[
            _T("t3", "오후 12시 30분"),
            sel("meal2", "점심", [
                opt("all", "전량 섭취", "일반식 상식 점심 전량 섭취함.", "점심 전량 드심."),
                opt("half", "절반", "점심 절반 정도 섭취함."),
                opt("npo", "금식", "금식 유지 중."),
            ], default="all"),
            sel("pca_remove", "PCA", [
                opt("removed", "전량 주입 후 제거", "PCA 들어가고 있는 것 전량 주입됨 설명하고 제거함. IV PCA 리필 원하지 않음.",
                    "PCA 전량 주입되어 제거함. 리필 원하지 않으심."),
                opt("keep", "유지", "PCA 유지 중.", "PCA 계속 유지함."),
                opt("na", "해당 없음"),
            ], default="removed", skip_values=("na",)),
            num("bt3", "체온", min=35, max=42, step=0.1, default=37.0, phrases=["체온 {v}도 측정됨.", "BT {v}도."]),
        ]),
        Section("d_reassess", "재사정 (13:30) — 이벤트", fields=[
            _T("t4", "오후 1시 30분"),
            num("nrs4", "NRS", min=0, max=10, default=1, phrases=["수술 부위 통증 {v}점 정도.", "통증 {v}점으로 사정됨.", "NRS {v}점."]),
            sel("reassess", "재사정 내용", [
                opt("after_pca", "PCA 제거 후 통증 사정", "PCA 제거 후 통증 사정함. 추가적인 중재 원하지 않음.", "PCA 제거 후 통증 재사정함, 추가 중재 원치 않음."),
                opt("after_prn", "PRN 후 재사정", "PRN 투여 후 통증 호전됨.", "진통제 투여 후 통증 감소함."),
                opt("stable", "안정", "특이사항 없이 안정적임.", "변화 없이 안정됨."),
            ], default="after_pca"),
        ]),
        Section("e_round", "Evening 라운딩 (15:00) — 정규 사정", hint="V/S, 활동, 배액/배뇨", fields=[
            _T("t5", "오후 3시"),
            Field(key="vitals_evening", label="오후 활력징후", kind="vitals", default={"sbp": 118, "dbp": 76, "hr": 78, "rr": 18, "bt": 36.7, "spo2": "", "o2": ""}),
            sel("afternoon_activity", "활동", [
                opt("sit", "침상 옆 앉기", "침상 옆에 앉기 시행함, 어지럼 없음.", "침상 옆 앉기 10분 시행함. 어지럼 호소 없음."),
                opt("walk_assist", "보호자 동반 보행", "보호자 동반하여 복도 보행 1회 시행함.", "보호자 부축 하에 병동 한 바퀴 보행함. 어지럼 없음."),
                opt("walk_self", "혼자 보행", "혼자 복도 보행 2회 시행함.", "병동 복도 스스로 보행하며 지내심."),
                opt("bedrest", "침상 안정", "침상 안정 유지 중. 체위 변경 시행함.", "침상 안정 유지하며 2시간마다 체위 변경함."),
                opt("chemo_infusion", "항암제 주입 중", "항암제 주입 중이며 오심, 발진 등 특이 반응 없음.", "항암제 주입 중, 주입 부위 통증·발적 없음. 부작용 관찰 중."),
            ], default="walk_assist"),
            txt("drain_note", "배액/배뇨", placeholder="예: JP 배액 serosanguineous하게 30cc 비움", phrases=["{v}.", "{v}."]),
        ]),
        Section("e_dinner", "저녁 식사 (18:00) — 이벤트", fields=[
            _T("t6", "오후 6시"),
            sel("meal3", "저녁", [
                opt("all", "전량 섭취", "저녁 식사 전량 섭취함.", "저녁 전량 드심."),
                opt("half", "절반", "저녁 절반 정도 섭취함.", "저녁 반 정도 드심."),
                opt("npo", "금식", "금식 유지 중."),
            ], default="all"),
        ]),
        Section("e_event", "저녁 이벤트 (20:00)", fields=[
            _T("t7", "오후 8시"),
            sel("evening_note", "특이사항", [
                opt("stable", "특이사항 없음", "특이사항 없이 안정적임.", "별다른 호소 없이 안정적으로 지내심."),
                opt("visit", "보호자 면회", "보호자 면회 중이며 환자 안정적임.", "보호자 면회 중. 특이 호소 없음."),
                opt("edu", "내일 일정 설명", "내일 검사 및 처치 일정 설명함.", "다음 날 일정 설명하고 질문에 답함."),
                opt("pain_prn", "통증 PRN", "통증 호소하여 PRN 진통제 투여함. 30분 후 재사정 예정.", "통증 4점 호소하여 PRN 투여함."),
            ], default="stable"),
        ]),
        Section("n_round", "Night 라운딩 (23:00) — 정규 사정", hint="V/S, 수면 상태, 통증, 라인", fields=[
            _T("t8", "오후 11시"),
            Field(key="vitals_night", label="밤 활력징후", kind="vitals", default={"sbp": 115, "dbp": 72, "hr": 70, "rr": 16, "bt": 36.6, "spo2": "", "o2": ""}),
            sel("night_onset", "수면 상태", [
                opt("asleep", "수면 중", "수면 중임. 호흡 규칙적임.", "잠들어 있음, 특이 호소 없음."),
                opt("resting", "안정", "침상에서 안정 취하고 있음.", "누워서 안정 중, 불편감 호소 없음."),
                opt("awake_pain", "통증으로 못 잠", "통증으로 잠들지 못한다고 함.", "수술 부위 통증 호소하며 깨어 있음."),
                opt("hypnotic", "수면제 투여", "처방된 수면제 투여 후 수면 유도함.", "수면제 투여함. 이후 잠듦."),
            ], default="asleep"),
            num("nrs_n", "NRS", min=0, max=10, default=1, phrases=["통증 {v}점.", "NRS {v}점으로 사정됨.", "통증 {v}점 정도로 조절됨."]),
            boolean("night_line", "라인·수액 확인", phrases=["수액 주입 속도 확인하고 라인 개방성 확인함.", "라인 역류 확인되고 수액 잘 들어감.", "IV 삽입 부위 이상 없음."], default=True),
        ]),
    ],
)
