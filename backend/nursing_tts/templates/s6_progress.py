"""S6. 시간별 경과기록 (기록체, 여러 시각 항목을 한 녹음에)."""
from .base import RecordTemplate, Section, opt, sel, multi, num, txt, boolean
from .common import VITALS_FIELD

TEMPLATE = RecordTemplate(
    key="s6",
    title="S6. 시간별 경과기록 (기록체)",
    signal_kind="수술후설명",
    description="한 근무 동안의 시각별 경과를 차팅하듯 구술합니다. '~함/~됨' 기록체가 기본이며, 시각마다 '환자명 ○○○'을 다시 말합니다.",
    intros=["", "{name} 님 경과기록 시작합니다.", "환자명 {name}, 경과기록 하겠습니다."],
    closings=["이상 {name} 님 경과기록 마치겠습니다.", "여기까지 {name} 님 경과기록입니다.", "이상입니다.", "간호정보조사는 다음 녹음 파일에 하겠습니다."],
    sections=[
        Section("e1", "1차 기록 (근무 시작)", hint="밤 동안 수면, 통증, 낙상 예방, 수액·라인, 상처, V/S", fields=[
            txt("t1", "시각", placeholder="예: 오전 7시", phrases=["{v} 환자명 {name}.", "{v}, 환자명 {name}.", "{v} {name} 님."], default="오전 7시"),
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
            txt("line", "라인", placeholder="예: 왼팔 22게이지",
                phrases=["{v}로 정맥 잘 주입되고 있음. 혈액 역류 잘 확인됨.", "{v} 라인 개방성 확인됨.", "{v} 통해 수액 잘 들어감. 역류 확인됨."], default="왼팔 22게이지"),
            txt("wound", "상처", placeholder="예: 복부 단일공, 소독 잘 되어 있음",
                phrases=["수술 부위 {v} 소독 잘 되어 있으며 상처 치유 상태 문제 없고 건조함.", "수술 부위 {v} 드레싱 깨끗하고 건조함.",
                         "{v} 상처 발적, 삼출물 없음."], default="복부 단일공"),
            VITALS_FIELD,
        ]),
        Section("e2", "2차 기록 (아침 식사)", fields=[
            txt("t2", "시각", placeholder="예: 오전 8시", phrases=["{v} 환자명 {name}.", "{v}, 환자명 {name}."], default="오전 8시"),
            sel("meal1", "식사", [
                opt("all", "전량 섭취", "일반식 상식 전량 섭취함.", "아침 식사 전량 드심.", "식사 전량 섭취함."),
                opt("half", "절반", "일반식 절반 정도 섭취함.", "아침 반 정도 드심."),
                opt("little", "소량", "식사 소량만 섭취함. 식욕 저하 호소.", "아침 거의 못 드심."),
                opt("npo", "금식", "금식 유지 중.", "NPO 유지함."),
            ], default="all"),
        ]),
        Section("e3", "3차 기록 (점심/중재)", fields=[
            txt("t3", "시각", placeholder="예: 오후 1시", phrases=["{v} 환자명 {name}.", "{v}, 환자명 {name}."], default="오후 1시"),
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
        Section("e4", "4차 기록 (재사정)", fields=[
            txt("t4", "시각", placeholder="예: 오후 1시 30분", phrases=["{v} 환자명 {name}.", "{v}, 환자명 {name}."], default="오후 1시 30분"),
            num("nrs4", "NRS", min=0, max=10, default=1, phrases=["수술 부위 통증 {v}점 정도.", "통증 {v}점으로 사정됨.", "NRS {v}점."]),
            sel("reassess", "재사정 내용", [
                opt("after_pca", "PCA 제거 후 통증 사정", "PCA 제거 후 통증 사정함. 추가적인 중재 원하지 않음.", "PCA 제거 후 통증 재사정함, 추가 중재 원치 않음."),
                opt("after_prn", "PRN 후 재사정", "PRN 투여 후 통증 호전됨.", "진통제 투여 후 통증 감소함."),
                opt("stable", "안정", "특이사항 없이 안정적임.", "변화 없이 안정됨."),
            ], default="after_pca"),
        ]),
    ],
)
