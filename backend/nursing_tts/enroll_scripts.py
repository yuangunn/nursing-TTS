"""Reading scripts for voice enrollment (10-15 s each, heavy on ward vocabulary).

Each script is short on purpose: zero-shot cloning models (F5-TTS, CosyVoice,
Fish Speech...) work best with a clean 5-15 second reference.  The transcript
is stored alongside the recording because the models need it as ``ref_text``.
"""

SCRIPTS: list[dict[str, str]] = [
    {
        "id": "sig_admission",
        "title": "시그널 + 간호정보조사",
        "text": "2026년 10월 13일 오후 4시 10분 홍길동 님 간호정보조사 기록입니다. 10월 13일 외래 통해 수술 목적으로 입원하였고, 주증상은 2개월 전부터 지속된 상복부 불편감입니다.",
    },
    {
        "id": "vitals",
        "title": "활력징후",
        "text": "활력징후 혈압 138에 84, 맥박 76, 호흡 18, 체온 36.7, 산소포화도 98퍼센트입니다. 의식 명료하고 지남력 있으며 수술에 대한 불안 호소합니다.",
    },
    {
        "id": "history",
        "title": "과거력·알레르기",
        "text": "과거력은 고혈압 10년, 당뇨 5년으로 경구약 복용 중이며 조영제에 두드러기 반응 있었고 약물 알레르기는 없습니다. 아스피린은 외래에서 1주 전 중단한 상태입니다.",
    },
    {
        "id": "preop",
        "title": "수술 전 교육",
        "text": "내일 오전 8시 첫 수술로 외과 교수 집도 하 라파로스코픽 토탈 가스트렉토미 예정입니다. 금일 자정부터 물 포함 금식 설명하였으며, 인스피로미터 사용법 시범 보이고 공 세 개 올리는 것 확인했습니다.",
    },
    {
        "id": "postop",
        "title": "수술 후 상태",
        "text": "우측 복부 제이피 한 개 있고 배액 생귀니어스 양상으로 현재 20씨씨 배액되었습니다. 폴리 카테터 16 프렌치 유지 중이며 소변 맑고 노란색으로 잘 나오고 있습니다. 통증 NRS 4점으로 PCA 유지 중입니다.",
    },
    {
        "id": "fever",
        "title": "발열 노티",
        "text": "오전 10시 10분 외과 주치의께 전화 노티했습니다. 비티 38.1, 혈압 150에 85, 심박 92, 수술 부위 우징 없고 폐음 하부 감소되어 있다고 보고하였고, 아세트아미노펜 1그램 아이브이 투여 처방 받았습니다.",
    },
    {
        "id": "discharge",
        "title": "퇴원 교육",
        "text": "퇴원약은 아세트아미노펜 650밀리그램 하루 세 번 식후 5일분이고, 외래는 10월 27일 오전 10시 30분입니다. 38도 이상 발열, 혈변이나 토혈, 심한 복통 시 응급실 내원하도록 안내하였습니다.",
    },
    {
        "id": "handover",
        "title": "인수인계",
        "text": "인계드리겠습니다. 위암, 티지 피오디 2, 풀코드, 보호자 배우자 상주 중입니다. 하트만 80씨씨 퍼 아워, 세파졸린 큐 에이트 아워 들어가고 있고, 랩에서 더블유비씨 11.2, 씨알피 8.5로 상승해 담당의 노티한 상태입니다.",
    },
    {
        "id": "casual",
        "title": "현장 말투",
        "text": "혈압은 123에 90 나오셨구요, 맥박은 72, 열은 7도 1 나오셨습니다. 가스 아웃 확인돼서 저녁부터 물 시작했고 잘 드셨어요. 소변줄은 어제 빼고 셀프 보이딩 잘 하시구요, 내일 아침 랩 에프유 하기로 했습니다.",
    },
    {
        "id": "numbers",
        "title": "숫자·단위 연습",
        "text": "인아웃은 수액 2000에 소변 1800, 제이피 60입니다. 혈당은 식전 150에서 180으로 슬라이딩 스케일 적용 중이고, 오투 3리터 나잘로 샛 97퍼센트 유지 중입니다. 2시간마다 체위 변경하고 있습니다.",
    },
]


def get_script(script_id: str) -> dict[str, str] | None:
    return next((s for s in SCRIPTS if s["id"] == script_id), None)
