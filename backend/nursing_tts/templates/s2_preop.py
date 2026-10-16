"""S2. 수술/검사 전 교육."""
from .base import RecordTemplate, Section, opt, sel, multi, num, txt, boolean

TEMPLATE = RecordTemplate(
    key="s2",
    title="S2. 수술/검사 전 설명",
    signal_kind="수술전설명",
    description="수술 또는 침습적 검사 전날~당일, 수술 일정·처방을 보면서 교육한 내용을 구술합니다.",
    closings=["여기까지 {name} 님 수술 전 교육 마치겠습니다.", "이상 수술전 간호기록 마치겠습니다.", "이상 수술 전 교육 기록 마치겠습니다.", "수술전 간호기록 이상입니다."],
    sections=[
        Section("op", "수술/검사 정보", hint="수술명/검사명, 예정 일시, 집도의/시행 과, 순서", fields=[
            txt("op_date", "예정 일시", placeholder="예: 내일 10월 14일 오전 8시",
                phrases=["{v} ", "{v} 수술 예정으로,", "{v}에,"]),
            sel("order", "수술 순서", [
                opt("first", "첫 수술", "첫 수술로,", "첫 번째 수술이고,", "1번 수술로 잡혀 있고,"),
                opt("second", "두 번째", "두 번째 수술로,", "2번 수술이고,"),
                opt("third", "세 번째 이후", "세 번째 수술로,", "오후 수술로 잡혀 있고,"),
                opt("unknown", "순서 미정", "수술 순서는 아직 미정이고,", "순서는 수술실에서 연락 주기로 했고,"),
            ], default="first"),
            txt("procedure", "수술명/검사명", placeholder="비워두면 환자 정보의 수술명 사용",
                phrases=["{v} 예정입니다.", "{v} 하실 예정이고,", "{v} 하시게 되고,"]),
            boolean("use_patient_surgery", "환자 정보의 수술명 사용",
                    phrases=["{dept} {prof} 교수님 집도로 {surgery} 예정입니다.", "{prof} 교수님 집도로 {surgery} 예정이고,",
                             "{surgery} 하실 예정이고 집도의는 {dept} {prof} 교수님입니다."], default=True),
        ]),
        Section("npo", "금식", hint="고형식/물 금식 시작 시각, 금식 중 허용 약", fields=[
            sel("npo_start", "금식 시작", [
                opt("midnight", "자정부터", "금일 자정부터 물 포함 금식 설명하였습니다.", "자정부터 물까지 금식하시도록 교육했고,",
                    "오늘 밤 12시부터는 물도 드시면 안 된다고 설명드렸구요,"),
                opt("mn_solid_water2", "자정 고형식, 수술 2시간 전 물", "자정부터 금식이고 맑은 물은 수술 2시간 전까지 허용된다고 설명하였습니다.",
                    "고형식은 자정부터 금식, 물은 수술 두 시간 전까지 가능하다고 교육했고,"),
                opt("evening", "저녁 식사 후부터", "저녁 식사 후부터 금식 설명하였습니다.", "저녁 드시고 나서부터 금식하시도록 교육했고,"),
                opt("already", "이미 금식 중", "현재 금식 유지 중입니다.", "이미 금식 중이시고,"),
            ], default="midnight"),
            txt("npo_meds", "금식 중 허용 약", placeholder="예: 혈압약은 아침 6시 소량의 물로",
                phrases=["{v} 복용하도록 교육했습니다.", "{v} 드시도록 설명드렸고,", "{v} 복용하시게 됩니다."]),
        ]),
        Section("medadj", "투약 조정", hint="항응고제·항혈소판제·당뇨약·혈압약 복용/중단", fields=[
            sel("bp_med", "혈압약", [
                opt("take_am", "아침 소량 물로 복용", "혈압약은 수술 당일 아침 6시 소량의 물로 복용하도록 교육했습니다.",
                    "혈압약 암로디핀은 내일 아침 6시 소량의 물로 드시도록 했고,", "혈압약은 아침에 물 한 모금으로 드시라고 설명드렸구요,"),
                opt("hold", "중단", "혈압약은 수술 당일 아침 hold 하도록 했습니다.", "혈압약 당일 아침은 거르시도록 교육했고,"),
                opt("na", "해당 없음", "", "혈압약은 안 드시고,"),
            ], default="take_am", skip_values=("na",)),
            sel("dm_med", "당뇨약", [
                opt("hold_evening", "전날 저녁부터 중단", "메트포르민은 오늘 저녁부터 중단하도록 교육했습니다.",
                    "당뇨약은 오늘 저녁부터 드시지 않도록 했고,", "경구 혈당강하제 오늘 저녁부터 중단이구요,"),
                opt("hold_am", "당일 아침 중단", "당뇨약은 수술 당일 아침 중단입니다.", "당뇨약 당일 아침은 거르시도록 교육했고,"),
                opt("insulin_half", "인슐린 반 용량", "인슐린은 수술 당일 아침 반 용량 맞도록 교육했습니다.", "아침 인슐린은 절반만 맞으시고,"),
                opt("na", "해당 없음"),
            ], default="hold_evening", skip_values=("na",)),
            sel("anticoag", "항응고/항혈소판제", [
                opt("stopped", "이미 중단 확인", "아스피린은 1주 전 중단한 것 확인했습니다.", "항혈소판제 중단 확인했고,", "아스피린 중단 상태 확인했구요,"),
                opt("hold_today", "오늘부터 중단", "항응고제는 오늘부터 중단하도록 교육했습니다.", "항응고제 오늘부터 hold 이고,"),
                opt("bridging", "브릿징", "헤파린 브릿징 중입니다.", "저분자헤파린으로 브릿징 중이고,"),
                opt("na", "해당 없음"),
            ], default="stopped", skip_values=("na",)),
        ]),
        Section("prep", "전처치", hint="장 준비, 피부 준비(제모·소독), 관장, 예방적 항생제", fields=[
            multi("prep", "전처치", [
                opt("bowel_prep", "하제 복용", nouns=["저녁 8시 하제 복용"]),
                opt("enema", "관장", nouns=["수술 당일 아침 관장"]),
                opt("shave", "제모", nouns=["수술 부위 클리퍼 제모", "클리퍼 제모"]),
                opt("skin_prep", "피부 소독", nouns=["클로르헥시딘 피부 소독"]),
                opt("shower", "샤워", nouns=["수술 전 샤워"]),
                opt("antibiotic", "예방적 항생제", nouns=["예방적 항생제 피부반응검사"]),
                opt("none", "해당 없음"),
            ], phrases=["{v} 예정이고 설명하였습니다.", "전처치로 {v} 시행 예정입니다.", "{v} 하기로 하고 설명드렸구요,"],
               none_phrases=["특별한 전처치는 없습니다.", "전처치 해당 없고,"], default=["bowel_prep", "shave"]),
            txt("prep_detail", "전처치 상세", placeholder="예: 오늘 저녁 8시 하제 복용 예정",
                phrases=["{v}.", "{v}이고,"]),   # free text for the user; the virtual patient leaves it empty (the 전처치 item already says it)
        ]),
        Section("remove", "제거물", hint="틀니, 안경/렌즈, 장신구, 매니큐어, 보청기", fields=[
            multi("removables", "제거물", [
                opt("denture", "틀니", nouns=["틀니"]),
                opt("glasses", "안경/렌즈", nouns=["안경", "렌즈"]),
                opt("jewelry", "장신구", nouns=["반지", "장신구", "목걸이"]),
                opt("nail", "매니큐어", nouns=["매니큐어"]),
                opt("hearing", "보청기", nouns=["보청기"]),
                opt("underwear", "속옷", nouns=["속옷"]),
            ], phrases=["수술 당일 아침 {v} 제거하도록 설명했습니다.", "{v} 제거하고 환의만 입으시도록 교육했고,",
                        "{v} 빼시도록 설명드렸구요,", "수술실 가기 전 {v} 제거하시도록 안내했습니다."],
               none_phrases=["제거할 틀니, 장신구 없으십니다.", "틀니나 장신구는 없으시고,"], default=["denture", "glasses", "jewelry", "nail"]),
        ]),
        Section("consent", "동의서/확인", hint="수술·마취·수혈 동의서, 혈액형, 팔찌, 마킹", fields=[
            multi("consents", "동의서", [
                opt("op", "수술 동의서", nouns=["수술 동의서"]),
                opt("anes", "마취 동의서", nouns=["마취 동의서"]),
                opt("tf", "수혈 동의서", nouns=["수혈 동의서"]),
            ], phrases=["{v} 확인했습니다.", "{v} 작성된 것 확인했고,", "{v} 확인했구요,"],
               none_phrases=["동의서 아직 미작성으로 담당의 확인 요청했습니다."], default=["op", "anes", "tf"]),
            boolean("marking", "수술 부위 마킹", phrases=["수술 부위 마킹 확인했습니다.", "수술 부위 마킹 되어 있는 것 확인했고,"],
                    false_phrases=["수술 부위 마킹 아직 안 되어 있어 담당의 noti 했습니다."], default=True),
            txt("blood_type", "혈액형", placeholder="예: A형 Rh+",
                phrases=["혈액형 {v}, 팔찌 확인했습니다.", "혈액형 {v} 확인했고,", "{v}이고 팔찌 확인했구요,"], default="A형 Rh+"),
        ]),
        Section("expect", "수술 후 예상 경과", hint="회복실/ICU, 소요 시간, 부착물, 통증 조절", fields=[
            sel("after_route", "수술 후 경로", [
                opt("rr", "회복실 거쳐 병실", "수술 후 회복실 거쳐 병실로 올라온다고 설명하였습니다.", "회복실 거쳐 병실로 오시게 되고,",
                    "수술 끝나면 회복실에서 한 시간 정도 계시다가 병실로 오신다고 설명드렸구요,"),
                opt("icu", "중환자실", "수술 후 중환자실로 가신다고 설명하였습니다.", "수술 후 ICU 입실 예정이고,"),
            ], default="rr"),
            txt("duration", "예상 소요 시간", placeholder="예: 3~4시간",
                phrases=["수술 시간은 {v} 정도 예상된다고 설명했습니다.", "수술은 {v} 정도 걸리고,"], speak_prob=0.8),
            multi("attachments", "예상 부착물", [
                opt("jp", "JP 배액관", nouns=["JP 배액관"]),
                opt("hemovac", "Hemovac 배액관", nouns=["Hemovac 배액관", "헤모박"]),
                opt("foley", "소변줄", nouns=["소변줄"]),
                opt("iv", "수액 라인", nouns=["수액 라인"]),
                opt("ltube", "L-tube", nouns=["L-tube"]),
                opt("pca", "PCA", nouns=["PCA"]),
                opt("o2", "산소", nouns=["산소"]),
            ], phrases=["수술 후 {v} 있을 수 있다고 설명하였습니다.", "수술 후 {v} 가지고 올라오실 수 있다고 설명하였습니다.",
                        "수술 후 {v} 달고 올라오신다고 설명드렸구요,"], default=["jp", "foley", "iv", "pca"]),
        ]),
        Section("edu", "수술 전 교육", hint="심호흡·기침, 강화폐활량계, 하지 운동, 조기 이상", fields=[
            boolean("inspirometer", "강화폐활량계 교육", phrases=["Inspirometer 사용법 시범 보였고 환자 공 3개 올리는 것 확인했습니다.",
                    "강화폐활량계 사용법 교육했고 직접 해보시는 것 확인했고,", "인스피로미터 시범 보여드리고 연습하시도록 했구요,"], default=True),
            boolean("breathing", "심호흡·기침 교육", phrases=["심호흡, 기침 방법 교육하였습니다.", "심호흡과 기침 교육했고,",
                    "수술 후 폐 합병증 예방 위해 심호흡, 기침 교육했구요,"], default=True),
            boolean("leg", "하지 운동 교육", phrases=["다리 운동, 발목 돌리기 교육하였습니다.", "하지 운동 교육했고,"], default=True),
            boolean("ambulation", "조기 이상 교육", phrases=["다음 날 조기 보행 필요성 설명하였습니다.", "수술 다음날부터 보행해야 한다고 설명드렸고,",
                    "조기 이상 중요성 설명했구요,"], default=True),
        ]),
        Section("family", "보호자", fields=[
            sel("waiting", "대기 장소 안내", [
                opt("done", "안내함", "보호자 대기 장소 안내하였습니다.", "보호자분께 수술 대기실 안내했고,", "수술 대기실 위치 안내드렸구요,"),
                opt("absent", "보호자 부재", "보호자 부재로 전화로 연락드리기로 했습니다.", "보호자 안 계셔서 전화 연락하기로 했고,"),
            ], default="done"),
        ]),
        Section("qa", "환자 질문/반응", fields=[
            txt("question", "환자 질문과 대응", placeholder="예: 수술 후 식사 시작 시점 질문하여 가스 배출 후 단계적 진행 설명함",
                phrases=["{v}.", "환자분이 {v}."],
                example="수술 후 식사 시작 시점 질문하여 가스 배출 후 물부터 미음, 죽, 단계적으로 진행한다고 설명함"),
            sel("understanding", "이해도", [
                opt("both", "환자·보호자 이해", "환자분과 보호자분 모두 이해했다고 표현하였습니다.", "환자, 보호자 교육 내용 이해하셨고,"),
                opt("patient", "환자만", "환자분 이해했다고 하셨습니다.", "환자분 이해 표현하셨고,"),
                opt("re_edu", "재교육 필요", "이해도 낮아 재교육 필요합니다.", "다음 근무 때 재교육 필요하고,"),
            ], default="both"),
        ]),
    ],
)
