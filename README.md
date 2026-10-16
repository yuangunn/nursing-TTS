# 간호기록 음성 녹음 생성기 (Nursing TTS)

가상 환자의 간호기록을 **체크박스로 구성**하면, 등록된 간호사 목소리로 **발화하고 녹음 파일 + 정답 텍스트**를 저장하는 Windows / macOS 데스크탑 앱입니다. STT 학습용 데이터 제작을 목적으로 합니다.

- 기록 종류: 간호정보조사(S1, 문진형 질문-답 포함) · 수술/검사 전 설명(S2) · 수술/검사 직후 설명(S3-1) · 수술 후 상태기록(S3-2, 사정→노티→중재→재사정) · 퇴원간호(S4) · 인수인계 SBAR(S5) · 시간별 경과기록(S6, 기록체)
- 녹음 시작 시그널: `「[연도]년 [월]월 [일]일 [시간]시 [분]분 [환자 성명] 님 [기록종류] 기록입니다.」` (기록종류: 간호정보조사/퇴원간호/수술전설명/수술후설명/인계)
- 현장 말투 다양화: 같은 체크 상태에서도 매번 다른 문장("혈압은 123에 90 나오셨구요, 열은 7도 1", "BP 123/90", "HTN"↔"고혈압"↔"하이퍼텐션")으로 생성. 말투(격식/구어/혼합/기록체 "~함·~됨") 선택, 어미 자동 확장, 말투 관리 탭에서 항목별 변형 편집
- 목소리 복제: 앱 안에서 의학용어가 많이 포함된 예시 대본을 읽어 녹음하거나, 실제 2~3분 녹음 파일(m4a/mp3/wav)을 올려 6~14초 샘플을 자동 추출(Whisper 전사 포함) → 여러 간호사 목소리 등록 → 로컬 오픈소스 모델로 그대로 발성
- 주변 소음: 모니터 맥박음·알람, 수액 펌프 알람, 네뷸라이저, 붐비는 사람 소리, 복도 발소리, 카트, 전화벨 등 합성 소음을 랜덤 시점에 삽입. 실제 병동 녹음 파일 업로드 가능. 다른 등록 목소리로 "회진 대화"를 멀리서 들리게 섞는 옵션
- 가상 환자 대량 생성: 환자·날짜·상태를 무작위로 만들어 N개 일괄 생성
- BYOK LLM(선택): Anthropic 또는 OpenAI 호환 API 키를 넣으면 규칙 기반 대본을 더 자연스럽게 다듬음


## 처음 실행 (설치 안내)

앱을 처음 켜면 **처음 설정 마법사**가 뜹니다. 순서는 `환경 점검 → 백엔드 설치 → 음성 엔진 → 첫 목소리 → 완료`이며 약 5분이 걸립니다.

- **환경 점검**: Python 3.10 이상, 디스크 여유 공간, 기존 설치 여부를 확인하고 없으면 설치 방법(brew / python.org)을 바로 안내합니다.
- **백엔드 설치**: 앱 데이터 폴더에 Python 가상환경을 만들고 패키지를 설치합니다. 단계별 진행률, 경과 시간, 예상 남은 시간이 표시되고 언제든 취소할 수 있습니다. 기본 설치는 2~4분, Qwen3-TTS 복제 엔진을 함께 설치하면 10~25분(패키지 약 2 GB + 모델 약 4.5 GB)입니다. pip이 버전 충돌로 제자리걸음을 하면 자동으로 중단하고 이유를 알려 줍니다.
- **음성 엔진**: 처음에는 "자동"으로 두면 됩니다. 복제 엔진이 없으면 시스템 음성으로 전체 흐름을 먼저 확인할 수 있습니다.
- **첫 목소리**: 대본을 읽어 10초 샘플을 등록합니다. 마이크가 없으면 건너뛰고 나중에 "1 · 목소리 등록"에서 하면 됩니다.

마법사가 끝나면 왼쪽 메뉴가 작업 순서(1 목소리 등록 → 2 녹음 만들기 → 3 대량 생성 → 4 결과물·검수)대로 정렬되어 있고, 첫 화면 위의 **시작 가이드**가 다음에 할 일을 알려 줍니다. 설정 탭의 "처음 설정 다시 보기"로 언제든 마법사를 다시 열 수 있습니다.

## 간호 프로토콜 체크리스트 (정규 차팅)

간호진단별 중재 항목을 체크하면 "~함" 기록체(또는 선택한 말투)로 문장이 생성됩니다. 기록 종류마다 해당되는 프로토콜만 붙습니다.

| 프로토콜 | 항목 예 |
|---|---|
| Routine check up | 수면양상 관찰, 환자 상태 확인(안정/오한/오심/구토), 식사량 확인, 정규 V/S |
| 낙상 예방(고위험군) / 환경관리(저위험군) | 예방지침 교육, 중재(물건 침상 옆, 침상 낮춤, 난간, 바퀴 고정, 야간 조명, 미끄럼 방지 신발), call bell, 팔찌, Morse 재사정 |
| 급성통증 / 만성통증 | 사정(부위·정도·척도 NRS/FLACC/VAS/PAINAD·양상·지속기간), 중재(처방명·경로), 비약물 중재, 정보 제공, 재사정, IV PCA 확인·종료 |
| Wound care | 상처 관찰(부위·상태), Dressing 상태 확인, 상처 Dressing(부위·시행자), 상처 교육 |
| 약물투여 | 주입속도, 주사부위(Gauge·부위·Dressing·patency), 약물 교육, 부작용 사정, 투여, AST |
| 비효율적 호흡양상 | 호흡 사정(RR·SpO2·호흡음·보조근), 산소(방법·유량), 심호흡·기침, 강화폐활량계(횟수·공), 체위, 객담/네뷸라이저, 호흡곤란 시 알리기 |
| 배액관 관리 | 종류·부위·삽입일, 양상·양, 고정/milking, 교육, 제거(시행자) |
| 도뇨관 관리 | 종류·크기·삽입일, 소변 양상·양, 고정·소변백 위치, 회음부 간호, 제거, 자가배뇨 확인, 잔뇨 |
| 고체온 | 체온(값·부위), 원인 사정, 해열제(약·경로), 미온수/ice pack, 수분 격려, 재측정, 노티, 배양 |
| 오심 | 사정, 항구토제, 식이 조절, 구강 간호, 체위, 흡인 예방 교육, 재사정 |
| 불안정한 혈당 수치 관리 | 혈당(시점·값), 증상 사정, 인슐린(종류·단위·방식), 저혈당 중재, 교육, 노티, 재측정 |
| 욕창 예방 · 불안 (보강) | Braden, 피부 사정, 체위 변경, 압력 완화 / 불안 사정, 정보 제공, 정서적 지지, 이완요법 |

시그널은 설정 또는 녹음마다 형식을 고를 수 있습니다: 필수 형식(「○○○ 님 ○○ 기록입니다」), 「환자명 ○○○ ○○하겠습니다」, 「○○○ 님 ○○ 시작합니다」 등, 그리고 무작위 혼합. 말투 관리 탭의 "시그널 형식"에 직접 템플릿을 추가할 수 있고, 내장 파서가 날짜·시각·환자명·기록종류·트리거 동사를 인식하는지 확인해 줍니다. 내보내기 manifest에는 시그널 문장·문자 구간·파싱 결과가 라벨로 들어갑니다.

## 유사 도구에서 가져온 기능

| 기능 | 어디서 | 이 앱에서 |
|---|---|---|
| ASR 되읽기 검증 (CER 기준 자동 플래그, 재검증) | TTS 데이터셋 생성기(qwen3-tts-dataset-generator 등)의 validate 단계 | 설정 → ASR 검증 (faster-whisper), 결과물 탭 CER 배지·필터 |
| 승인/반려 리뷰, 반려 제외 내보내기 | 데이터 라벨링 도구의 QA 흐름 | 결과물·QA 탭 (A/R 버튼, 상태는 .json에 저장) |
| LJSpeech `metadata.csv`, NeMo `manifest.jsonl`, Whisper 파인튜닝 jsonl, 화자 층화 train/val/test, report.json, 데이터셋 카드 | Piper/Coqui/NeMo/HF 학습 관례 | 결과물 탭 → 데이터셋 내보내기 (16 kHz 재샘플 포함) |
| 말속도 섭동, 마이크/채널 시뮬레이션(스마트폰·핀마이크·녹음기·전화 대역·원거리), 음량 편차, 클리핑 | Kaldi/ESPnet ASR 증강 관례 | 증강 패널 (녹음 단위로 무작위 선택, 메타에 기록) |
| 구어 흐트러짐: 추임새("음…"), 말 반복, 숫자 자기정정("37.4, 아니 37.1") | 현장 구술 데이터 특성 | 증강 패널 → 구어 흐트러짐 0~3. 정답 텍스트는 깔끔하게, verbatim은 별도 저장 |
| 음량 정규화, 같은 입력의 N개 변형 생성, 소음 폴더(MUSAN/DEMAND) 일괄 가져오기 | 데이터셋 파이프라인 관례 | 설정 → 음량 정규화, 녹음 생성 → 변형 수, 소음 패널 → 폴더째 가져오기 |

## 결과물

`출력폴더/{시그널발화시각}_{환자명}.wav` 와 같은 이름의 `.txt`(발화한 정답 텍스트), `.json`(구조화 데이터 + TTS 발음 텍스트 + 소음 이벤트 + 메타)이 함께 저장됩니다.

```
20261018_1110_홍길동.wav
20261018_1110_홍길동.txt   ← "2026년 10월 18일 오전 11시 10분 홍길동 님 인계 기록입니다. 과거력 HTN, 당뇨 있고 ..."
20261018_1110_홍길동.json  ← spoken_text / tts_text / structured(form) / noise.events / seed ...
```

내보낸 데이터셋은 `출력폴더/_exports/<이름>/`에 `wavs/`(16 kHz mono) + `metadata.csv`(LJSpeech) + `manifest_*.jsonl`(NeMo) + `whisper_*.jsonl` + `dataset.csv` + `report.json` + `README.md`(데이터셋 카드)로 저장됩니다.

`tts_text`는 숫자·약어를 모두 한글 발음으로 바꾼 텍스트("혈압 백이십삼 에 구십, 에이치티엔")로, 모델이 실제로 읽은 발음의 기록입니다.

## 구조

```
backend/   Python (FastAPI) – 대본 생성, 한국어 발음 변환, TTS 어댑터, 소음 합성/믹싱, 목소리/소음 라이브러리, 배치
app/       Electron + React – 데스크탑 UI (백엔드를 자동 실행)
scripts/   설치 스크립트, 커스텀 TTS 서버 예제
```

## 설치

요구 사항: **Python 3.10+**, **Node.js 18+**. 목소리 복제 모델을 로컬에서 돌리려면 NVIDIA GPU(CUDA) 또는 Apple Silicon(MPS)을 권장합니다 (CPU도 동작하지만 매우 느림).

### 1) 백엔드

```bash
# macOS / Linux
./scripts/setup-backend.sh          # 기본
./scripts/setup-backend.sh --qwen   # + Qwen3-TTS 내장 목소리 복제 엔진

# Windows (PowerShell)
.\scripts\setup-backend.ps1
.\scripts\setup-backend.ps1 -Qwen
```

### 2) 앱 실행 (개발 모드)

```bash
cd app
npm install
npm run dev
```

앱이 뜨면 `backend/.venv`의 Python으로 백엔드(`http://127.0.0.1:8765`)를 자동 실행합니다. 설정 탭에서 백엔드 로그와 엔진 상태를 볼 수 있습니다.

### 3) 설치 파일 만들기 (선택)

```bash
cd app
npm run dist:win    # Windows NSIS 설치 파일 → app/release/
npm run dist:mac    # macOS dmg
```

설치 버전은 `resources/backend` 안의 Python 가상환경을 찾습니다. 배포 PC에서도 `scripts/setup-backend.*`를 한 번 실행해 `.venv`를 만들어 주세요.

### 4) 인트라넷(인터넷 없는 PC) 설치 — 오프라인 번들

설치 후 Python이나 pip, 모델을 내려받을 수 없는 PC용입니다. 인터넷이 되는 PC에서 번들 zip을 만들어 USB 등으로 옮깁니다.

```bash
# 인터넷 되는 PC (같은 OS·아키텍처여야 함)
scripts/build-offline-bundle.sh --qwen            # macOS/Linux: Python + 패키지 + Qwen3-TTS/faster-whisper
scripts/build-offline-bundle.sh --qwen --models   # + 모델 파일(약 5 GB)까지 한 번에
powershell -ExecutionPolicy Bypass -File scripts\build-offline-bundle.ps1 -Qwen          # Windows (CPU PyTorch)
powershell -ExecutionPolicy Bypass -File scripts\build-offline-bundle.ps1 -Qwen -Cuda    # Windows + NVIDIA (cu128, 약 3 GB)
```

번들은 `dist-offline/nursing-tts-offline-<os>-<arch>[-qwen][-models].zip`로 만들어집니다(안에 relocatable CPython `python/`, 선택 `models/hub/`, `bundle.json`). 인트라넷 PC에서는 앱 설치 파일을 깔고 **처음 설정 마법사의 "백엔드 설치" 단계** 또는 **설정 → 백엔드**에서 "📦 오프라인 번들(zip) 가져오기"로 그 zip을 고르면, 앱 데이터 폴더 `offline/`에 풀려 그 Python으로 백엔드가 뜹니다. 모델을 번들에 넣지 않았다면 설정 → 로컬 모델의 폴더에 `models--Qwen--Qwen3-TTS-12Hz-1.7B-Base`, `models--Systran--faster-whisper-small` 폴더를 복사하세요. GitHub Actions의 "Offline bundle" 워크플로로도 mac(arm64/x64)·Windows(CPU) 번들을 릴리스에 올릴 수 있습니다(2 GB 넘는 CUDA 번들은 로컬에서 만들어 옮김).

## TTS 엔진

| 엔진 | 목소리 복제 | 비고 |
|---|---|---|
| **Qwen3-TTS** (`qwen`) | O | 내장 한국어 복제 (Apache-2.0, 기본 1.7B). 마법사 "목소리 복제 엔진 포함" 또는 `pip install -r backend/requirements-qwen.txt`. Apple Silicon(MPS)·NVIDIA 권장 |
| **커스텀 HTTP** (`http`) | O | Fish Speech / OpenAudio, CosyVoice 2, XTTS 등 원하는 모델을 `scripts/example_tts_server.py` 계약으로 감싸 연결 |
| 시스템 TTS (`system`) | X | macOS `say`, Windows SAPI, Linux espeak-ng. 파이프라인 확인용 |
| 무음 (`silent`) | X | 음성 없이 파일/텍스트 파이프라인 테스트용 |

`자동` 선택 시 Qwen3-TTS → HTTP → 시스템 → 무음 순으로 사용 가능한 엔진을 고릅니다. 모델은 기본 설정에서 10분 쉬면 메모리에서 내려가고 다음 합성 때 다시 올라옵니다(설정에서 조절).

### 한국어를 지원하는 로컬 목소리 복제 모델

2026년 기준으로 한국어를 공식 지원하면서 오픈 가중치로 로컬 실행이 가능한 zero-shot 복제 모델입니다. 모두 `scripts/servers/`의 래퍼로 바로 연결할 수 있습니다 (각 모델은 의존성이 달라 **별도 가상환경**에서 서버로 띄우는 방식을 권장).

| 모델 | 라이선스 | 한국어 | 참조 음성 | 래퍼 | 비고 |
|---|---|---|---|---|---|
| **Qwen3-TTS** (Alibaba, 0.6B/1.7B) | Apache-2.0 | 10개 언어 중 공식 지원 | 3초~ | 내장 엔진 `qwen` 또는 `qwen3_tts_server.py` | **기본 내장 엔진**. M4 Mac(MPS)에서 1.7B 실시간 대비 약 2.3배, 0.6B 약 1.9배 |
| **Chatterbox Multilingual v3** (Resemble AI) | MIT | 23개 언어, `ko` | 5~10초 | `chatterbox_server.py` | 감정 과장(exaggeration) 조절 가능, 설치 간단 |
| **Fun-CosyVoice3 / CosyVoice2** (Alibaba) | Apache-2.0 | 9개 언어 중 공식 지원 | 3~10초 | `cosyvoice_server.py` | 저장소 클론·모델 다운로드 필요, 스트리밍 지원 |
| **GPT-SoVITS v2+** | MIT | 한/영/일/중/광둥 | 5초 zero-shot, 1분 few-shot 파인튜닝 | (자체 API 서버 `api_v2.py` 사용) | 간호사별 1분 데이터로 **파인튜닝**하면 가장 비슷한 목소리 |
| ~~F5-TTS~~ | CC-BY-NC | 기본 vocab에 한글 없음 | — | (제거됨) | 공개 한국어 체크포인트가 없어 0.1.2에서 뺐습니다 |

실행 예:

```bash
# Qwen3-TTS (별도 venv; Apple Silicon은 MPS bf16으로 자동 실행, M4에서 0.6B 모델 RTF 약 1.9)
python3.12 -m venv ~/.venvs/nursing-qwen && ~/.venvs/nursing-qwen/bin/pip install -U qwen-tts fastapi uvicorn python-multipart soundfile
~/.venvs/nursing-qwen/bin/python scripts/servers/qwen3_tts_server.py --port 8081
# 앱 설정 → 커스텀 HTTP TTS 서버 URL: http://127.0.0.1:8081/synthesize
```

래퍼는 각 모델의 공식 README/모델 카드에 적힌 API 그대로 호출하며, 이 저장소에서는 GPU가 없어 실제 합성까지는 검증하지 못했습니다. 모델 버전이 바뀌어 인자명이 달라지면 래퍼 파일의 `synthesize()` 한 함수만 고치면 됩니다.

### 원격 GPU에서 합성하기

내장 엔진은 백엔드가 도는 PC에서 합성합니다. GPU가 다른 PC(예: NVIDIA 노트북)에 있으면 거기서 `scripts/servers/qwen3_tts_server.py`를 띄우고 설정 → 커스텀 HTTP TTS 서버 URL을 그 PC 주소로 바꾸면 됩니다. 수천 건을 양산할 때 유리합니다.

### 커스텀 HTTP TTS 서버 계약

```
POST {url}  multipart/form-data
  text       : 읽을 한국어 발음 텍스트
  ref_audio  : 참조 wav (등록된 목소리 샘플)
  ref_text   : 참조 음성의 전사
  seed       : 정수 (선택)
→ 200, body = audio/wav
GET {url의 상위 경로}/health → 200
```

`scripts/example_tts_server.py`의 `synthesize()`만 교체하면 됩니다.

## 사용 흐름

1. **목소리 등록** 탭 → 목소리 추가 → 예시 대본(의학용어 포함, 8~15초)을 선택하고 녹음 → 3~5개 샘플 권장. "이 목소리로 합성 테스트"로 확인
2. **녹음 생성** 탭 → 기록 종류 선택 → 가상 환자 정보 입력 또는 🎲 무작위 생성 → 상태 체크 → 미리보기(🔀 다른 말투로 / ✨ LLM 다듬기 / 직접 수정) → 소음 옵션 → 목소리 선택 → 🎙 발화 + 녹음 저장
3. **대량 생성** 탭 → 개수·기록 종류·목소리·소음 비율 지정 → 시작. 결과는 출력 폴더의 하위 폴더에 저장
4. **설정** 탭 → 엔진/장치/체크포인트, 출력 폴더, 샘플레이트(STT용 16 kHz), LLM BYOK

## 개발

```bash
cd backend && .venv/bin/python -m pytest        # 백엔드 테스트 (발음 변환, 문법, 생성기, 믹서, API)
cd app && npm run typecheck && npm run build    # 프론트엔드
```

브라우저만으로 UI를 확인하려면 백엔드를 `python -m nursing_tts`로 띄우고 `npm run dev` 후 `http://localhost:5173`을 열면 됩니다 (Electron 전용 기능인 폴더 열기 등은 비활성).

### 발화 템플릿 수정

`backend/nursing_tts/templates/s*.py`에 항목·선택지·문장 변형이 선언되어 있습니다. 각 선택지에 여러 문장을 넣으면 생성 시 무작위로 선택되며, 쉼표(`,`)로 끝나는 문장은 다음 항목과 이어지는 연결형("~하시구요,")으로 취급됩니다. 약어 발음은 `korean.py`의 `ABBREVIATIONS`에 추가하면 됩니다.
