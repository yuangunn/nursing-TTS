"""S3-1. 수술 후 기록 (POD 0, 병실 도착 직후) — 병동 범주 순서, 범주당 한 번 (user 2026-10-17):
환자 확인·도착 → 바이탈 사인·의식 → 가지고 온 주입·배액관 관찰 → 수술 부위 관찰 → 통증 사정 → 약물 투여 → 수술 후 처치(O2·IPC·ice bag) →
금식 유지 기간 교육 → 자세·활동 교육 → 배액관 관리 → 도뇨관 관리 → 수술별 관찰·교육 → 알려야 할 증상 → 검사 후 주의 → 이해도.
관찰(가지고 온 것의 상태)과 관리 교육을 다른 필드로 나누어 같은 말이 두 번 나오지 않는다."""
from .base import RecordTemplate, Section, opt, sel, multi, num, txt, boolean
from .common import VITALS_FIELD, CONSCIOUSNESS, PAIN_NRS, PAIN_MED

_NOTE = ["{v}.", "{v}이고,"]

TEMPLATE = RecordTemplate(
    key="s3_1",
    title="S3-1. 수술 후 기록 (POD 0, 병실 도착 직후)",
    signal_kind="수술후설명",
    description="수술 당일(POD 0) 회복실 거쳐 병실에 도착한 직후, 환자 상태·수술기록·처방을 보면서 구술합니다. 관찰(바이탈·배액관·수술 부위·통증) → 투여·처치 → 교육(금식·자세·배액관·도뇨관) → 알려야 할 증상 순서로, 범주마다 한 번씩. 다음 날부터의 하루 경과는 S6 경과기록으로. 검사 직후 기록도 여기서.",
    intros=["{name}님 진단명 {dx}, {surgery} 수술후 간호기록 시작합니다.",
            "진단명 {dx}, {surgery} 환자분 수술 후 간호기록입니다.",
            "{dx}(으)로 {surgery} 시행하신 {name}님 수술 후 간호기록 시작합니다."],
    closings=["이상 수술후 간호기록 마치겠습니다.", "여기까지 {name} 님 수술 후 간호기록 마치겠습니다.", "이상 {surgery_abbr} 수술후 간호기록 마치겠습니다.", "이상 수술 후 간호기록 마치겠습니다.", "수술후 간호기록 이상입니다."],
    sections=[
        Section("op", "수술/검사 정보", hint="시행 수술명/검사명, 시행 일시, POD", fields=[
            sel("timing", "시점", [
                opt("day0", "수술 당일", "{op_date} {surgery_en} 시행하고 회복실 거쳐 {arrival_time} 병실 도착하였습니다.",
                    "오늘 {surgery} 시행 후 회복실 거쳐 {arrival_time}에 병실 올라오셨고,", "오늘 {surgery} 하시고 회복실 경유해서 {arrival_time}에 병실 도착하셨구요,"),
                opt("post_exam", "검사 직후", "검사 마치고 병실 도착하였습니다.", "검사 끝나고 올라오셨고,"),
            ], default="day0"),
            txt("arrival_time", "병실 도착 시각", placeholder="예: 12시 30분", phrases=[], speak_prob=0.0, default="오후 12시 30분",
                hint="'수술 당일' 문장 안에서 읽힘"),
        ]),
        Section("status", "바이탈 사인·의식", hint="도착 시 V/S, 의식, 오심", fields=[
            txt("vs_lead", "측정 시점", placeholder="예: 도착 당시", phrases=["{v} ", "{v}에 "], speak_prob=1.0),   # "측정한 활력징후 체크하니"
            VITALS_FIELD,
            sel("consciousness", "의식", CONSCIOUSNESS, default="alert"),
            boolean("responds", "질문에 적절히 대답", phrases=["지남력 있으며 질문에 적절히 대답하였습니다.", "질문에 적절히 대답하시고,"], default=True),
            sel("nausea", "오심/구토", [
                opt("none", "없음", "오심 없습니다.", "오심, 구토 없고,", "메스꺼움 없다고 하시구요,"),   # 증상에 존대 없음
                opt("nausea", "오심", "오심 호소하십니다.", "오심 있다고 하시고,", "속 울렁거린다고 하시구요,"),
                opt("vomit", "구토", "구토 1회 있었습니다.", "구토 있으셔서 담당의 noti 했고,"),
            ], default="none"),
        ]),
        Section("lines", "가지고 온 주입·배액관 관찰", hint="수액 라인, 배액관(위치·양상·양), 도뇨관, 비위관 — 상태만", fields=[
            txt("iv", "수액 라인", placeholder="예: Lt arm 20G line",
                phrases=["IV는 {v} 가지고 계시고 수액 주입 잘 되고 있습니다.", "{v} 통해 H/S 잘 들어가고 있고 삽입 부위 발적, 부종 없습니다.",
                         "{v} 유지 중이고 DW 주입 중이구요,", "IV는 {v} 가지고 계시고 주입 잘 되구요,"],
                default="Lt arm 20G line"),
            sel("ltube", "비위관", [
                opt("none", "없음"),
                opt("keep", "L-tube 유지", "L-tube 유지 중이며 배액 양상 관찰 중입니다.", "L-tube 가지고 계시고 자연 배액 중이고,"),
            ], default="none", skip_values=("none",)),
            sel("drain", "배액관", [
                opt("jp_sang", "JP bloody", "수술 부위 JP 1개 있고 현재 {drain_amount}cc bloody하게 배액되었습니다.",
                    "JP drain 1개 수술 부위에 가지고 오셨고 수술 직후 {drain_amount}cc bloody하게 배액되었습니다.",
                    "JP 1개 bloody하게 {drain_amount}cc 나왔고,", "JP drain 한 개 가지고 오셨고 {drain_amount}cc bloody하게 나오고 있구요,", "JP 배액 bloody하게 {drain_amount}cc 나오고 있습니다."),
                opt("jp_sero", "JP serosanguineous", "JP 배액 serosanguineous 양상 {drain_amount}cc입니다.", "JP serosanguineous {drain_amount}cc 나왔고,",
                    "JP drain 1개 있고 serosanguineous하게 {drain_amount}cc 배액 중입니다.", "JP drain 가지고 계시고 serosanguineous {drain_amount}cc 나오고,"),
                opt("hemovac", "Hemovac", "수술 부위 Hemovac 1개 있고 {drain_amount}cc bloody하게 배액되었습니다.",
                    "Hemovac 1개 가지고 오셨고 수술 직후 {drain_amount}cc bloody하게 배액되었습니다.",
                    "Hemovac bloody하게 {drain_amount}cc 나왔고,", "헤모박 한 개 있고 {drain_amount}cc bloody하게 나오고 있구요,"),
                opt("none", "배액관 없음", "배액관 없습니다.", "배액관은 없고,"),
            ], default="jp_sang"),
            num("drain_amount", "배액량", unit="cc", min=0, max=2000, default=20, phrases=[], speak_prob=0.0),
            sel("foley", "도뇨관", [
                opt("keep", "유지", "Foley catheter 16 Fr. 유지 중이며 소변 맑고 노란색으로 잘 나오고 있습니다.", "소변줄 유지 중이고 소변 clear하게 잘 나오고 있고,",
                    "폴리 유지 중이고 소변 노랗고 맑구요,"),
                opt("removed", "제거됨, 자가배뇨", "소변줄 제거하고 자가배뇨 확인하였습니다.", "소변줄 빼고 self voiding 잘 하시고,"),
                opt("none", "없음", "소변줄 없이 올라오셨고 수술 후 6시간 이내 자가배뇨 확인 예정입니다.", "소변줄 없이 올라오셨고 첫 자가배뇨 확인 필요합니다.",
                    "소변줄 없이 올라오셨고,"),
            ], default="keep"),
        ]),
        Section("wound", "수술 부위 관찰", hint="드레싱 상태 (젖음·출혈 시 보고는 '알려야 할 증상'에서)", fields=[
            sel("dressing", "드레싱 상태", [
                opt("clean", "깨끗", "수술 부위 드레싱 깨끗하고 oozing 없습니다.", "수술 부위 드레싱 깨끗하고 oozing 없고,", "드레싱 clean 하구요,"),
                opt("oozing", "oozing", "수술 부위 드레싱에 소량 oozing 있어 담당의 확인 후 드레싱 교환했습니다.", "드레싱 oozing 소량 있어 보강했고,"),
                opt("bleeding", "출혈", "수술 부위 출혈 있어 담당의 noti 하였습니다.", "드레싱 피 비쳐서 noti 했고,"),
            ], default="clean"),
        ]),
        Section("pain", "통증 사정", hint="NRS, 진통 방법, PCA 사용법", fields=[
            PAIN_NRS,
            sel("pain_med", "진통 방법", PAIN_MED, default="pca"),
            boolean("pca_edu", "PCA 사용법 교육", phrases=["PCA 버튼은 통증 있을 때 직접 누르도록 하고, 눌러도 조절 안 되거나 오심, 어지러움 있으면 호출하도록 설명했습니다.",
                    "PCA 버튼 직접 누르시도록 교육했고 조절 안 되면 호출하시라고 했고,",
                    "PCA 버튼 사용법 교육하고 오심 시 알리도록 설명드렸구요,"], default=True),
        ]),
        Section("meds", "약물 투여", hint="수술 후 투여한 항생제·진통제·항구토제·항응고제 (가상 환자 생성 시 자동)", fields=[
            txt("meds_given", "투여 약물", placeholder="예: 세파졸린 1g IV, 케토롤락 30mg IV",
                phrases=["{v} 투여하였습니다.", "처방대로 {v} 투여하였습니다.", "{v} 투여하였고,", "{v} 들어갔구요,"]),
        ]),
        Section("care", "수술 후 처치", hint="산소, DVT 예방 IPC, ice bag, 거상, 압박", fields=[
            sel("o2", "산소 적용", [
                opt("none", "산소 없음", "산소 적용 없이 room air 유지 중입니다.", "산소 없이 지내시고,"),
                opt("nasal", "nasal 적용", "O2 nasal 적용 중이며 내일 아침 SpO2 확인 후 제거 예정입니다.", "산소 nasal로 들어가고 있고,"),
                opt("mask", "mask 적용", "O2 mask 적용 중입니다.", "마스크로 산소 들어가고 있고,"),
                opt("trach", "trach mask", "trach mask로 가습 산소 적용 중입니다.", "trach mask로 산소 들어가고 있고,"),
            ], default="nasal"),
            multi("postop_care", "처치", [
                opt("ipc", "IPC (DVT 예방)", nouns=["DVT 예방 위한 간헐적 공기압박기"]),
                opt("icebag", "ice bag", nouns=["수술 부위 ice bag"]),
                opt("icebag_nose", "콧등 ice bag", nouns=["콧등 ice bag"]),   # ESS: the wound is inside the nose
                opt("elevation", "환부 거상", nouns=["환부 거상"]),
                opt("compression", "압박 드레싱/복대", nouns=["압박 드레싱"]),
                opt("warming", "보온", nouns=["보온 담요"]),
            ], phrases=["{v} 적용하였습니다.", "{v} 적용 중입니다.", "{v} 적용했고,", "{v} 적용 중이구요,"], default=[]),
        ]),
        Section("diet", "금식 유지 기간 교육", hint="금식 유지 여부, 진행 기준(가스 배출, 복부 상태)", fields=[
            sel("diet_status", "식이 단계", [
                opt("npo", "금식 유지", "가스 배출 확인될 때까지 금식 유지하고 물도 드시지 않도록 설명하였습니다.", "가스 나올 때까지 금식이고 물도 안 된다고 설명드렸고,",
                    "금식 중이고 가스 아웃 확인되면 물부터 시작한다고 설명했구요,"),
                # POD 0, an hour after the OR: nothing has passed gas and nothing is "in progress" yet (2026-10-18 검수)
                opt("sow", "물 시작", "수술 6시간 후부터 물 조금씩 드셔도 된다고 설명하였습니다.", "저녁부터 물 조금씩 드셔도 된다고 했고,"),
                opt("ld", "미음", "저녁부터 미음 시작 예정입니다.", "저녁에 미음 드시기로 했고,"),
                opt("gd", "일반식 가능", "마취 깨고 물부터 드셔 보고 괜찮으면 식사 가능하다고 설명하였습니다.", "물 드셔 보고 괜찮으면 저녁부터 식사하시도록 했고,",
                    "저녁부터 식사 가능하구요,"),
                opt("npo_nausea", "금식(오심)", "오심 있어 당분간 금식 유지하고 가라앉으면 물부터 시작하기로 설명하였습니다.", "오심 가라앉을 때까지 금식이고,"),
                opt("npo_drowsy", "금식(각성 전)", "완전히 깨실 때까지 금식 유지하고 이후 물부터 드시도록 설명하였습니다.", "마취 깨실 때까지 금식이고,"),
                opt("npo_trach", "금식(흡인 위험)", "흡인 위험이 있어 금식 유지하고 삼킴 확인 후 식이 진행 예정입니다.", "삼킴 확인 전까지 금식이고,"),
            ], default="npo"),
            sel("abdomen", "복부 상태", [
                opt("soft", "팽만 없음", "복부 팽만 없고 부드럽습니다.", "복부 팽만 없고,", "복부 부드럽고 팽만 없구요,"),
                opt("distended", "팽만", "복부 팽만 있습니다.", "복부 팽만 있어 관찰 중이고,"),
                opt("gas_out", "가스 배출됨", "가스 배출 확인되었습니다.", "gas out 확인됐고,"),
            ], default="soft"),
        ]),
        Section("position", "자세·활동 교육", hint="침상 머리, 조기 이상, 다리 운동, 낙상 예방, 하지 감각, 호흡 운동", fields=[
            sel("hob", "침상 머리", [
                opt("30", "30도 상승", "침상 머리 30도 올린 상태입니다.", "침상 머리 30도 올려 드렸고,", "HOB 30도 유지 중이구요,"),
                opt("flat", "앙와위", "앙와위 유지 중입니다.", "침상 평평하게 유지 중이고,"),
                opt("semi", "반좌위", "반좌위 유지 중입니다.", "반좌위로 계시고,"),
            ], default="30"),
            sel("ambulation_plan", "조기 이상 계획", [
                opt("evening_sit", "오늘 저녁 침상 옆 앉기, 내일 보행", "오늘 저녁 침상 옆 앉기, 내일 오전부터 보호자 동반 병동 보행 계획 설명하였습니다.",
                    "저녁에 침상 옆 앉기 하고 내일부터 보행 시작한다고 설명드렸고,", "오늘은 침상에서 앉기까지 하고 내일 오전에 걷기 시작하기로 했구요,"),
                opt("walk_today", "오늘 보행 시작", "오늘 오후부터 보호자 동반 병동 보행 시작하도록 교육했습니다.", "오늘부터 보행 시작하시고,"),
                opt("bedrest", "침상 안정", "침상 안정 유지 중입니다.", "당분간 침상 안정이고,"),
            ], default="evening_sit"),
            boolean("leg_exercise", "침상 다리 운동 교육", phrases=["침상에서 발목 돌리기, 발목 펌프 운동 하도록 교육했습니다.", "침상에서 발목 운동 하시도록 교육했고,"],
                    default=True),   # "다리 굽혔다 펴기" contradicted THA·반월상 연골 봉합의 굴곡 제한
            boolean("fall_edu", "낙상 예방 교육", phrases=["난간 올리고 침대 바퀴 고정하는 등 낙상 예방 교육 시행하였습니다.",
                    "난간 올리고 낙상 예방 교육했고,", "낙상 예방 교육 시행했구요,"], default=True),
            boolean("leg_check", "양측 하지 감각·운동 확인", phrases=["양측 하지 감각, 운동 정상이고 부종 없습니다.", "양쪽 다리 감각, 운동 이상 없고,"], default=True),
            sel("breathing", "호흡 운동", [
                opt("intensive", "2시간 intensive 심호흡", "마취 후 무기폐 예방 위해 2시간 동안 intensive 심호흡 하도록 교육했고, inspirometer는 통증 가라앉고 다음날부터 시행하도록 설명하였습니다.",
                    "2시간 동안 intensive 심호흡 교육했고 inspirometer는 내일부터 하시도록 설명드렸고,",
                    "심호흡 자주 하시도록 교육했고 인스피로미터는 다음날부터 시작하기로 했구요,"),
                opt("inspirometer", "강화폐활량계 시행", "inspirometer 한 시간에 10회 시행하도록 교육하고 환자 직접 시행하는 것 확인하였습니다.",
                    "inspirometer 시간당 10회 하시도록 격려했고,", "강화폐활량계 공 3개 올리는 것 확인했구요,"),
            ], default="intensive"),
        ]),
        Section("drain_mgmt", "배액관 관리", hint="배액관 있을 때만", fields=[
            boolean("drain_edu", "배액관 관리 교육", phrases=["배액관 당겨지지 않도록 주의하고 혈액색이 짙어지거나 양이 갑자기 늘면 알리도록 설명하였습니다.",
                    "배액관 당겨지지 않게 주의하시라고 교육했고,", "배액관 색 짙어지거나 양 늘면 알리시라고 했구요,"], default=False),
            txt("drain_note", "배액관 관련 (수술별)", placeholder="예: 배액 색 우윳빛으로 변하면 즉시 알리도록", phrases=_NOTE),
        ]),
        Section("foley_mgmt", "도뇨관 관리", hint="도뇨관 유지 중일 때만", fields=[
            boolean("foley_edu", "도뇨관 관리 교육", phrases=["소변백 비우고 섭취배설량 측정 방법 설명하였고 소변줄은 다음날 아침 제거 예정입니다.",
                    "소변백 비우는 법 설명드렸고 소변줄은 내일 아침 뺄 예정이고,", "소변줄 관리 설명했고 다음 날 아침 제거 예정이구요,"], default=False),
            txt("foley_note", "도뇨관 관련 (수술별)", placeholder="예: 소변줄은 1~2주 유지 후 외래에서 제거 예정", phrases=_NOTE),
        ]),
        Section("special", "수술별 관찰·교육", hint="수술 종류에 따른 관찰·교육 포인트 (가상 환자 생성 시 자동으로 채워짐)", fields=[
            txt("special_edu", "수술별 특이 교육", placeholder="예: 손끝·입 주위 저림 있으면 즉시 알리도록 교육함",
                phrases=["{v}.", "{v}이고,", "{v}구요,"]),
        ]),
        Section("report", "알려야 할 증상", hint="발열, 숨참, 심한 통증, 드레싱 젖음·출혈 + 수술별", fields=[
            boolean("report_edu", "보고 증상 교육", phrases=["38도 이상 발열, 숨참, 심한 통증, 드레싱 젖거나 피 비칠 때 즉시 알리도록 교육하였습니다.",
                    "발열, 숨참, 심한 통증, 출혈 있으면 바로 호출하시라고 교육했고,",
                    "38도 이상 열나거나 숨차거나 수술 부위 많이 아프면 즉시 알리시라고 설명드렸구요,"], default=True),
            txt("report_note", "알려야 할 증상 (수술별)", placeholder="예: 손끝·입 주위 저림 있으면 즉시 알리도록", phrases=_NOTE),
        ]),
        Section("exam", "검사 후 주의 (검사 시)", hint="지혈 부위 압박 시간, 안정 시간, 조영제 후 수분 섭취", fields=[
            sel("exam_care", "검사 후 주의", [
                opt("na", "해당 없음"),
                opt("compression", "천자 부위 압박", "천자 부위 모래주머니 적용하고 6시간 압박 유지하도록 설명했습니다.", "시술 부위 6시간 압박하고 다리 굽히지 않도록 교육했고,"),
                opt("contrast", "조영제 후 수분 섭취", "조영제 사용하여 수분 충분히 섭취하도록 교육했습니다.", "조영제 배출 위해 물 많이 드시라고 했고,"),
                opt("rest", "안정", "검사 후 2시간 절대 안정 설명했습니다.", "2시간 침상 안정 유지하도록 했고,"),
            ], default="na", skip_values=("na",)),
        ]),
        Section("family", "보호자 교육/이해도", fields=[
            sel("understanding", "이해도", [
                opt("both", "환자·보호자 이해", "환자분과 보호자분 모두 이해했다고 표현하였습니다.", "환자, 보호자 모두 이해하셨다고 하시고,"),
                opt("patient", "환자만", "환자분 이해했다고 표현하셨습니다.", "환자분 이해 표현하셨고,"),
                opt("caregiver", "보호자만", "보호자분께 교육하였고 이해했다고 하셨습니다.", "보호자 교육했고,"),
                opt("re_edu", "재교육 필요", "이해도 낮아 다음 근무 재교육 필요합니다.", "재교육 필요하고,"),
            ], default="both"),
        ]),
    ],
)
