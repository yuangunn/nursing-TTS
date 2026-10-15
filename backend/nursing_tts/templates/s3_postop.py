"""S3-1. 수술/검사 직후 교육."""
from .base import RecordTemplate, Section, opt, sel, multi, num, txt, boolean
from .common import VITALS_FIELD, CONSCIOUSNESS, PAIN_NRS, PAIN_MED

TEMPLATE = RecordTemplate(
    key="s3_1",
    title="S3-1. 수술/검사 직후 설명",
    signal_kind="수술후설명",
    description="수술 직후~POD 1-2 또는 검사 직후, 환자 상태·수술기록·처방을 보면서 구술합니다.",
    intros=["{name}님 진단명 {dx}, {surgery_en}, {surgery_abbr} 수술후 간호기록 시작합니다.",
            "진단명 {dx}, {surgery} 환자분 수술 후 간호기록입니다.",
            "{dx}(으)로 {surgery} 시행하신 {name}님 수술 후 간호기록 시작합니다."],
    closings=["여기까지 {name} 님 수술 후 간호기록 마치겠습니다.", "이상 {surgery_abbr} 수술후 간호기록 마치겠습니다.", "이상 수술 후 간호기록 마치겠습니다.", "수술후 간호기록 이상입니다."],
    sections=[
        Section("op", "수술/검사 정보", hint="시행 수술명/검사명, 시행 일시, POD", fields=[
            sel("timing", "시점", [
                opt("day0", "수술 당일", "{op_date} 수술 당일 {surgery_en} 시행하고 회복실 거쳐 병실 도착하였습니다.",
                    "수술 당일로 {surgery} 시행 후 회복실 거쳐 병실 올라오셨고,", "오늘 {surgery} 하시고 회복실 경유해서 병실 도착하셨구요,"),
                opt("pod1", "POD 1", "{surgery} POD 1 입니다.", "수술 다음날 POD 1 이고,", "{surgery_abbr} POD 1 환자분이구요,"),
                opt("pod2", "POD 2", "{surgery} POD 2 입니다.", "{surgery_abbr} POD 2 이고,"),
                opt("post_exam", "검사 직후", "검사 마치고 병실 도착하였습니다.", "검사 끝나고 올라오셨고,"),
            ], default="day0"),
            txt("arrival_time", "병실 도착 시각", placeholder="예: 12시 30분",
                phrases=["{v} 병실 도착하였습니다.", "{v}에 병실 도착하셨고,", "병실 도착 시각 {v}이구요,"]),
        ]),
        Section("status", "현재 상태", hint="의식, V/S, 통증 NRS, 산소 적용", fields=[
            txt("vs_lead", "측정 시점", placeholder="예: 도착 당시", phrases=["{v} ", "{v} 측정한"], speak_prob=1.0),
            VITALS_FIELD,
            sel("consciousness", "의식", CONSCIOUSNESS, default="alert"),
            boolean("responds", "질문에 적절히 대답", phrases=["지남력 있으며 질문에 적절히 대답하였습니다.", "질문에 적절히 대답하시고,"], default=True),
            sel("nausea", "오심/구토", [
                opt("none", "없음", "오심 없습니다.", "오심, 구토 없으시고,", "메스꺼움 없다고 하시구요,"),
                opt("nausea", "오심", "오심 호소하십니다.", "오심 있어 PRN 항구토제 들어갔고,"),
                opt("vomit", "구토", "구토 1회 있었습니다.", "구토 있으셔서 담당의 noti 했고,"),
            ], default="none"),
        ]),
        Section("pain", "통증 관리", hint="PCA 사용법, 추가 진통제 요청, 부작용", fields=[
            PAIN_NRS,
            sel("pain_med", "진통 방법", PAIN_MED, default="pca"),
            boolean("pca_edu", "PCA 사용법 교육", phrases=["PCA 버튼은 통증 있을 때 직접 누르도록 하고, 눌러도 조절 안 되거나 오심, 어지러움 있으면 호출하도록 설명했습니다.",
                    "PCA 버튼 직접 누르시도록 교육했고 조절 안 되면 호출하시라고 했고,",
                    "PCA 버튼 사용법 교육하고 오심 시 알리도록 설명드렸구요,"], default=True),
        ]),
        Section("position", "체위/이동/낙상", hint="침상 머리 올리기, 조기 이상 시점·방법, 낙상 예방", fields=[
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
            boolean("leg_exercise", "침상 다리 운동 교육", phrases=["침상에서 발목 돌리기, 다리 굽혔다 펴기 하도록 교육했습니다.", "침상에서 다리 운동 하시도록 교육했고,"], default=True),
            boolean("fall_edu", "낙상 예방 교육", phrases=["난간 올린 상태 유지하고 침대 바퀴 고정 설명했습니다. 낙상 예방 교육 시행하였습니다.",
                    "난간 올리고 낙상 예방 교육했고,", "낙상 예방 교육 시행했구요,"], default=True),
        ]),
        Section("resp", "호흡 관리", hint="심호흡, 기침, 강화폐활량계 횟수", fields=[
            sel("breathing", "호흡 운동", [
                opt("intensive", "2시간 intensive 심호흡", "마취 후 무기폐 예방 위해 2시간 동안 intensive 심호흡 하도록 교육했고, inspirometer는 통증 가라앉고 다음날부터 시행하도록 설명하였습니다.",
                    "2시간 동안 intensive 심호흡 교육했고 inspirometer는 내일부터 하시도록 설명드렸고,",
                    "심호흡 자주 하시도록 교육했고 인스피로미터는 다음날부터 시작하기로 했구요,"),
                opt("inspirometer", "강화폐활량계 시행", "inspirometer 한 시간에 10회 시행하도록 교육하고 환자 직접 시행하는 것 확인하였습니다.",
                    "inspirometer 시간당 10회 하시도록 격려했고,", "강화폐활량계 공 3개 올리는 것 확인했구요,"),
            ], default="intensive"),
            sel("o2", "산소 적용", [
                opt("none", "산소 없음", "산소 적용 없이 room air 유지 중입니다.", "산소 없이 지내시고,"),
                opt("nasal", "nasal 적용", "O2 nasal 적용 중이며 내일 아침 SpO2 확인 후 제거 예정입니다.", "산소 nasal로 들어가고 있고,"),
                opt("mask", "mask 적용", "O2 mask 적용 중입니다.", "마스크로 산소 들어가고 있고,"),
            ], default="nasal"),
        ]),
        Section("diet", "식이", hint="금식 유지 여부, 진행 기준(가스 배출, 복부 상태)", fields=[
            sel("diet_status", "식이 단계", [
                opt("npo", "금식 유지", "가스 배출 확인될 때까지 금식 유지하고 물도 드시지 않도록 설명하였습니다.", "가스 나올 때까지 금식이고 물도 안 된다고 설명드렸고,",
                    "금식 중이고 가스 아웃 확인되면 물부터 시작한다고 설명했구요,"),
                opt("sow", "물 시작", "가스 배출 확인되어 물 시작했습니다.", "가스 아웃 확인되어 저녁부터 물 시작했고,"),
                opt("ld", "미음", "미음 진행 중입니다.", "미음 드시고 계시고,"),
                opt("gd", "일반식 가능", "식이 제한 없이 일반식 드셔도 된다고 설명하였습니다.", "식사는 일반식으로 드시고,", "식이 제한 없으시구요,"),
            ], default="npo"),
            sel("abdomen", "복부 상태", [
                opt("soft", "팽만 없음", "복부 팽만 없고 gas out 안 된 상태입니다.", "복부 팽만 없고,", "복부 부드럽고 팽만 없으시구요,"),
                opt("distended", "팽만", "복부 팽만 있습니다.", "복부 팽만 있어 관찰 중이고,"),
                opt("gas_out", "가스 배출됨", "가스 배출 확인되었습니다.", "gas out 확인됐고,"),
            ], default="soft"),
        ]),
        Section("lines", "라인/튜브/배액", hint="수액, 배액관(위치·양상·양), 도뇨관, 비위관", fields=[
            sel("drain", "배액관", [
                opt("jp_sang", "JP sanguineous", "우측 복부 JP 1개 있고 배액 sanguineous 양상으로 현재 {drain_amount}cc 배액되었습니다. 배액관 당겨지지 않도록 주의하고 혈액색이 짙어지거나 양이 갑자기 늘면 알리도록 설명하였습니다.",
                    "JP 1개 sanguineous {drain_amount}cc 나왔고 당겨지지 않게 주의하시라고 교육했고,",
                    "복부 JP 배액 sanguineous 양상 {drain_amount}cc 이고 색 짙어지거나 양 늘면 알리시라고 했구요,"),
                opt("jp_sero", "JP serosanguineous", "JP 배액 serosanguineous 양상 {drain_amount}cc 입니다.", "JP serosanguineous {drain_amount}cc 나왔고,"),
                opt("hemovac", "Hemovac", "수술 부위 Hemovac 1개 있고 배액 sanguineous 양상으로 {drain_amount}cc 배액되었습니다. 배액관 당겨지지 않도록 주의하고 양이 갑자기 늘면 알리도록 설명하였습니다.",
                    "Hemovac sanguineous {drain_amount}cc 나왔고 당겨지지 않게 주의하시라고 교육했고,", "헤모박 배액 {drain_amount}cc 이구요,"),
                opt("none", "배액관 없음", "배액관 없습니다.", "배액관은 없으시고,"),
            ], default="jp_sang"),
            num("drain_amount", "배액량", unit="cc", min=0, max=2000, default=20, phrases=[], speak_prob=0.0),
            sel("foley", "도뇨관", [
                opt("keep", "유지, 내일 제거 예정", "Foley catheter 16 Fr. 유지 중이며 소변 맑고 노란색으로 잘 나오고 있습니다. 소변백 비우고 섭취배설량 측정 방법 설명하였습니다. 소변줄은 다음날 아침 제거 예정입니다.",
                    "소변줄 유지 중이고 소변 맑게 잘 나오고 있고 내일 아침 제거 예정이고,",
                    "폴리 유지 중, 소변 노랗고 맑고 다음 날 아침 뺄 예정이구요,"),
                opt("removed", "제거됨, 자가배뇨", "소변줄 제거하고 자가배뇨 확인하였습니다.", "소변줄 빼고 self voiding 잘 하시고,"),
                opt("none", "없음", "소변줄 없이 자가배뇨 중입니다.", "소변줄 없으시고,"),
            ], default="keep"),
            txt("iv", "수액 라인", placeholder="예: 좌측 전완 말초 라인, H/S + DW",
                phrases=["{v} 들어가고 있고 삽입 부위 발적, 부종 없습니다.", "{v} 유지 중이고,", "{v} 통해 수액 들어가고 있구요,"],
                default="좌측 전완 말초 라인 통해 H/S, DW 수액"),
            sel("ltube", "비위관", [
                opt("none", "없음"),
                opt("keep", "L-tube 유지", "L-tube 유지 중이며 배액 양상 관찰 중입니다.", "L-tube 가지고 계시고 자연 배액 중이고,"),
            ], default="none", skip_values=("none",)),
            boolean("leg_check", "양측 하지 감각·운동 확인", phrases=["양측 하지 감각, 운동 정상이고 부종 없습니다.", "양쪽 다리 감각, 운동 이상 없으시고,"], default=True),
        ]),
        Section("wound", "상처 관리", hint="드레싱 상태, 젖음·출혈 시 보고", fields=[
            sel("dressing", "드레싱 상태", [
                opt("clean", "깨끗", "복부 수술 부위 드레싱 깨끗하고 oozing 없습니다.", "수술 부위 드레싱 깨끗하고 oozing 없고,", "드레싱 clean 하구요,"),
                opt("oozing", "oozing", "수술 부위 드레싱에 소량 oozing 있어 담당의 확인 후 드레싱 교환했습니다.", "드레싱 oozing 소량 있어 보강했고,"),
                opt("bleeding", "출혈", "수술 부위 출혈 있어 담당의 noti 하였습니다.", "드레싱 피 비쳐서 noti 했고,"),
            ], default="clean"),
            boolean("wound_edu", "상처 교육", phrases=["드레싱 젖거나 피 비치면 알리도록 설명하였습니다.", "드레싱 젖으면 알리시라고 교육했고,"], default=True),
        ]),
        Section("exam", "검사 후 주의 (검사 시)", hint="지혈 부위 압박 시간, 안정 시간, 조영제 후 수분 섭취", fields=[
            sel("exam_care", "검사 후 주의", [
                opt("na", "해당 없음"),
                opt("compression", "천자 부위 압박", "천자 부위 모래주머니 적용하고 6시간 압박 유지하도록 설명했습니다.", "시술 부위 6시간 압박하고 다리 굽히지 않도록 교육했고,"),
                opt("contrast", "조영제 후 수분 섭취", "조영제 사용하여 수분 충분히 섭취하도록 교육했습니다.", "조영제 배출 위해 물 많이 드시라고 했고,"),
                opt("rest", "안정", "검사 후 2시간 절대 안정 설명했습니다.", "2시간 침상 안정 유지하도록 했고,"),
            ], default="na", skip_values=("na",)),
        ]),
        Section("special", "수술별 특이 교육", hint="수술 종류에 따른 관찰·교육 포인트 (가상 환자 생성 시 자동으로 채워짐)", fields=[
            txt("special_edu", "수술별 특이 교육", placeholder="예: 손끝·입 주위 저림 있으면 즉시 알리도록 교육함",
                phrases=["{v}.", "{v}이고,", "{v}구요,"]),
        ]),
        Section("report", "보고해야 할 증상", fields=[
            boolean("report_edu", "보고 증상 교육", phrases=["38도 이상 발열, 숨참, 심한 복통, 드레싱 젖거나 피 비칠 때 즉시 알리도록 교육하였습니다.",
                    "발열, 숨참, 심한 통증, 출혈 있으면 바로 호출하시라고 교육했고,",
                    "38도 이상 열나거나 숨차거나 배 많이 아프면 즉시 알리시라고 설명드렸구요,"], default=True),
        ]),
        Section("family", "보호자 교육/이해도", fields=[
            sel("understanding", "이해도", [
                opt("both", "환자·보호자 이해", "환자와 보호자 모두 이해했다고 표현하였습니다.", "환자, 보호자 모두 이해하셨다고 하시고,"),
                opt("patient", "환자만", "환자분 이해했다고 표현하셨습니다.", "환자분 이해 표현하셨고,"),
                opt("caregiver", "보호자만", "보호자분께 교육하였고 이해했다고 하셨습니다.", "보호자 교육했고,"),
                opt("re_edu", "재교육 필요", "이해도 낮아 다음 근무 재교육 필요합니다.", "재교육 필요하고,"),
            ], default="both"),
        ]),
    ],
)
