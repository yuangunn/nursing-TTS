# 간호기록 음성 녹음 생성기 (Nursing TTS)

가상 환자의 간호기록을 **체크박스로 구성**하면, 등록된 간호사 목소리로 **발화하고 녹음 파일 + 정답 텍스트**를 저장하는 Windows / macOS 데스크탑 앱입니다. STT 학습용 데이터 제작을 목적으로 합니다.

- 기록 종류: 간호정보조사(S1) · 수술/검사 전 설명(S2) · 수술/검사 직후 설명(S3-1) · 수술 후 상태기록(S3-2, 사정→노티→중재→재사정) · 퇴원간호(S4) · 인수인계 SBAR(S5)
- 녹음 시작 시그널: `「[연도]년 [월]월 [일]일 [시간]시 [분]분 [환자 성명] 님 [기록종류] 기록입니다.」` (기록종류: 간호정보조사/퇴원간호/수술전설명/수술후설명/인계)
- 현장 말투 다양화: 같은 체크 상태에서도 매번 다른 문장("혈압은 123에 90 나오셨구요, 열은 7도 1", "BP 123/90", "HTN"↔"고혈압"↔"하이퍼텐션")으로 생성. 말투(격식/구어/혼합) 선택 가능
- 목소리 복제: 앱 안에서 의학용어가 많이 포함된 예시 대본을 읽어 녹음 → 여러 간호사 목소리 등록 → 로컬 오픈소스 모델(F5-TTS 등)로 그대로 발성
- 주변 소음: 모니터 맥박음·알람, 수액 펌프 알람, 네뷸라이저, 붐비는 사람 소리, 복도 발소리, 카트, 전화벨 등 합성 소음을 랜덤 시점에 삽입. 실제 병동 녹음 파일 업로드 가능. 다른 등록 목소리로 "회진 대화"를 멀리서 들리게 섞는 옵션
- 가상 환자 대량 생성: 환자·날짜·상태를 무작위로 만들어 N개 일괄 생성
- BYOK LLM(선택): Anthropic 또는 OpenAI 호환 API 키를 넣으면 규칙 기반 대본을 더 자연스럽게 다듬음

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
./scripts/setup-backend.sh --f5     # + F5-TTS 로컬 목소리 복제 엔진

# Windows (PowerShell)
.\scripts\setup-backend.ps1
.\scripts\setup-backend.ps1 -F5
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

## TTS 엔진

| 엔진 | 목소리 복제 | 비고 |
|---|---|---|
| **F5-TTS** (`f5`) | O | 로컬 zero-shot 복제. `pip install -r backend/requirements-f5.txt`. **한국어 파인튜닝 체크포인트** 필요 (아래 참고) |
| **커스텀 HTTP** (`http`) | O | Fish Speech / OpenAudio, CosyVoice 2, XTTS 등 원하는 모델을 `scripts/example_tts_server.py` 계약으로 감싸 연결 |
| 시스템 TTS (`system`) | X | macOS `say`, Windows SAPI, Linux espeak-ng. 파이프라인 확인용 |
| 무음 (`silent`) | X | 음성 없이 파일/텍스트 파이프라인 테스트용 |

`자동` 선택 시 F5 → HTTP → 시스템 → 무음 순으로 사용 가능한 엔진을 고릅니다.

### 한국어를 지원하는 로컬 목소리 복제 모델

2026년 기준으로 한국어를 공식 지원하면서 오픈 가중치로 로컬 실행이 가능한 zero-shot 복제 모델입니다. 모두 `scripts/servers/`의 래퍼로 바로 연결할 수 있습니다 (각 모델은 의존성이 달라 **별도 가상환경**에서 서버로 띄우는 방식을 권장).

| 모델 | 라이선스 | 한국어 | 참조 음성 | 래퍼 | 비고 |
|---|---|---|---|---|---|
| **Qwen3-TTS** (Alibaba, 0.6B/1.7B) | Apache-2.0 | 10개 언어 중 공식 지원 | 3초~ | `qwen3_tts_server.py` | 한국어 품질·자연스러움이 가장 균형 잡힘. 1순위 추천 |
| **Chatterbox Multilingual v3** (Resemble AI) | MIT | 23개 언어, `ko` | 5~10초 | `chatterbox_server.py` | 감정 과장(exaggeration) 조절 가능, 설치 간단 |
| **Fun-CosyVoice3 / CosyVoice2** (Alibaba) | Apache-2.0 | 9개 언어 중 공식 지원 | 3~10초 | `cosyvoice_server.py` | 저장소 클론·모델 다운로드 필요, 스트리밍 지원 |
| **GPT-SoVITS v2+** | MIT | 한/영/일/중/광둥 | 5초 zero-shot, 1분 few-shot 파인튜닝 | (자체 API 서버 `api_v2.py` 사용) | 간호사별 1분 데이터로 **파인튜닝**하면 가장 비슷한 목소리 |
| **F5-TTS** + 한국어 파인튜닝 | CC-BY-NC(가중치) | 커뮤니티 파인튜닝 필요 | 5~15초 | 내장 엔진 `f5` | 기본 체크포인트는 영/중. 비상업 라이선스 주의 |

실행 예:

```bash
# Qwen3-TTS (별도 venv)
pip install -U qwen-tts fastapi uvicorn python-multipart soundfile
python scripts/servers/qwen3_tts_server.py --port 8081
# 앱 설정 → 커스텀 HTTP TTS 서버 URL: http://127.0.0.1:8081/synthesize
```

래퍼는 각 모델의 공식 README/모델 카드에 적힌 API 그대로 호출하며, 이 저장소에서는 GPU가 없어 실제 합성까지는 검증하지 못했습니다. 모델 버전이 바뀌어 인자명이 달라지면 래퍼 파일의 `synthesize()` 한 함수만 고치면 됩니다.

### F5-TTS 한국어 체크포인트

F5-TTS 기본 체크포인트(`F5TTS_v1_Base`)는 영어/중국어 데이터로 학습되어 한국어 발음이 불완전합니다. Hugging Face에서 "F5-TTS Korean" 커뮤니티 파인튜닝 체크포인트(`model_*.pt` 또는 `.safetensors` + `vocab.txt`)를 받아 설정 탭에 경로를 지정하세요. 체크포인트마다 vocab이 다르므로 **같은 배포에 포함된 vocab.txt**를 함께 지정해야 합니다. 직접 파인튜닝하려면 F5-TTS 저장소의 `finetune_gradio.py`로 한국어 데이터(예: KSS, 자체 병동 녹음)를 학습하면 됩니다.

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
