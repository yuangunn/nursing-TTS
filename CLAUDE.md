# 간호기록 음성 녹음 생성기 (nursing-TTS)

가상 환자의 간호기록을 체크박스로 고르면, 등록한 간호사 목소리로 읽어 주는 **녹음(wav) + 정답 텍스트(txt/json)** 를 만들어 STT 학습 데이터를 생산하는 데스크탑 앱. 모든 환자 정보는 가상/가명이다.

## 구조

| 경로 | 내용 |
|---|---|
| `backend/nursing_tts/` | Python 3.10+ FastAPI 백엔드. 대본 생성·발음 변환·TTS 어댑터·소음 합성·증강·검증·데이터셋 내보내기 |
| `backend/tests/` | pytest (28개). 무음 엔진으로 전체 파이프라인을 돈다 |
| `app/` | Electron 33 + React 18 + Vite 6 + TypeScript. `electron/main.ts`가 백엔드 프로세스와 설치기를 담당 |
| `scripts/` | `setup-backend.{sh,ps1}`, 한국어 복제 모델 래퍼 서버(`servers/qwen3_tts_server.py` 등) |
| `.github/workflows/` | `ci.yml` (pytest + typecheck/build), `release.yml` (`v*` 태그 또는 수동 실행 → mac dmg/zip, win exe를 prerelease에 업로드) |
| `docs/ROADMAP.md` | 마일스톤과 시작 프롬프트 |

### 백엔드 핵심 개념
- **두 가지 텍스트 층**: `spoken_text`(정답, 숫자·약어 그대로) vs `tts_text`(발음용, `korean.py`가 숫자/날짜/단위/약어를 한글로 풀어 씀). 정답 텍스트는 절대 발음형으로 저장하지 않는다.
- **시그널 라인**: 녹음 첫 줄은 반드시 `signal.py`의 형식 중 하나. 필수 형식은 「[연도]년 [월]월 [일]일 [시간]시 [분]분 [환자명] 님 [기록종류] 기록입니다」. 기록종류는 간호정보조사/퇴원간호/수술전설명/수술후설명/인계. `signal.parse()`가 어떤 변형이든 날짜·시각·이름·종류를 뽑아내야 한다.
- **템플릿**: `templates/s1_admission.py` … `s6_progress.py`는 선언형(`RecordTemplate/Section/Field/Option`). 연결형 문구는 `,`로 끝내고 `grammar.close_sentence()`가 종결형으로 바꾼다. 조사는 `grammar.fix_josa()`. 말투는 formal/casual/mixed/chart, `phrase_store.stylize()`가 플레이스홀더 치환 **후** 적용.
- **프로토콜 체크리스트**: `templates/protocols.py` (정규 차팅: Routine, 낙상, 통증, Wound, 약물, 호흡, 배액관, 도뇨관, 고체온, 오심, 혈당 …). `Section.group == "protocol"`, 필드 키는 `p_` 접두.
- **말투 변형 관리**: `extra_phrases.py`(내장) + `phrase_store.py`(사용자 오버라이드 → `data_dir/phrases.json`). UI "말투 관리" 탭.
- **TTS 어댑터**: `tts/{qwen,http_engine,system,silent}.py`, `tts/registry.py`. `auto`는 qwen → http → system → silent. `qwen`은 Qwen3-TTS 1.7B 내장 복제(참조 프롬프트 캐시, 유휴 시 언로드), `http`는 원격 GPU 등 외부 서버용. HTTP 어댑터는 `scripts/servers/_common.py` 규약(`POST /synthesize`).
- **오디오**: `audio/noise.py`(합성 소음 카탈로그), `mixer.py`(SNR), `augment.py`(채널 프리셋·속도), `disfluency.py`(간투사·숫자 정정), `slicer.py`(긴 녹음 → 6~14초 조각), `verify.py`(faster-whisper CER), `dataset.py`(LJSpeech/NeMo/Whisper 내보내기).
- **파일명**: `{YYYYMMDD_HHMM}_{환자명}.wav/.txt/.json`. 데이터 폴더는 `NURSING_TTS_DATA` 환경변수 또는 OS 앱 데이터 폴더.

### 앱 핵심 개념
- `electron/main.ts`: 백엔드 Python 탐색(`userData/venv` → `backend/.venv`), 설치기(`setupBackend`: venv 생성 → pip → requirements → (Qwen: torch → requirements-qwen → 모델 다운로드) → 시작, `setup-progress` 이벤트로 단계/퍼센트/ETA 전송, 3.10 미만 venv 재생성, pip 되감기 감지 중단), `check-environment`.
- `src/App.tsx`: 처음 설정 마법사(`SetupWizard`) → 작업 순서 사이드바(`Sidebar`: 1 목소리 → 2 녹음 → 3 대량 → 4 결과물) + 시작 가이드(`GettingStarted`). 온보딩 완료 여부는 `localStorage`(`lib/onboarding.ts`).
- 페이지: `RecordPage`(1~7 단계), `VoicesPage`, `BatchPage`, `ResultsPage`, `PhrasesPage`, `SettingsPage`. 백엔드 호출은 `lib/api.ts` 하나로.

## 실행

```bash
# 백엔드
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # 또는 scripts/setup-backend.sh
.venv/bin/python -m pytest -q tests                                                   # 테스트
NURSING_TTS_DATA=/tmp/nursing-data .venv/bin/python -m nursing_tts --port 8765        # 서버만

# 앱 (개발: vite + electron, 백엔드는 main.ts가 backend/.venv로 자동 실행)
cd app && npm ci && npm run dev
npm run typecheck && npm run build        # CI와 동일
npx electron-builder --mac --publish never  # 로컬 패키징 (release/ 에 dmg/zip)
```

내장 복제 엔진은 `backend/requirements-qwen.txt`(qwen-tts + faster-whisper). 모델 `Qwen/Qwen3-TTS-12Hz-1.7B-Base`(약 4.5 GB)는 설치기 `model` 단계 또는 첫 합성 때 HF에서 받는다. Windows+NVIDIA는 torch를 cu128 인덱스로 먼저 설치. 다른 한국어 모델 비교는 README "한국어 모델" 절.

## 작업 규칙
- 브랜치를 따서 PR → CI green이면 squash merge (사용자 지시: "CI green시 자동 머지"). 저장소 auto-merge는 꺼져 있다.
- 커밋/PR 본문은 한국어로, 무엇을 왜 바꿨는지. UI 문구도 한국어.
- 테스트를 건너뛰거나 비활성화해서 green을 만들지 않는다. 백엔드 변경은 `pytest`, 앱 변경은 `typecheck + build`를 로컬에서 먼저.
- 대본 생성 규칙을 바꿀 때는 `backend/tests/test_api.py`의 미리보기 테스트로 문장 끝맺음(`~했고.` 같은 연결형 종결 금지), 조사 오류, 치환 안 된 `{placeholder}`가 없는지 확인한다.
- 새 체크 항목/필드를 추가하면 (1) 템플릿 선언, (2) `extra_phrases.py` 변형 2~5개, (3) `fake.py` 무작위 생성 풀, (4) 필요하면 `korean.py` 약어 읽기까지 한 세트로.
- 실제 환자 데이터는 절대 저장소에 넣지 않는다. 테스트 녹음은 `local_data/`(gitignore).

## 알려진 제한 / 다음 할 일
- F5-TTS는 제거했다(기본 vocab에 한글 없음, 공개 한국어 체크포인트 없음). 내장 복제는 Qwen3-TTS 1.7B(M4 MPS에서 RTF 약 2.3), 1.7B vs 0.6B 품질 비교와 실제 간호사 녹음 청취 검증은 `docs/ROADMAP.md` M1 참고.
- 코드 서명/공증 없음. 첫 실행 시 우클릭 → 열기 또는 `xattr -dr com.apple.quarantine`.
- 시스템 TTS(macOS `say`)는 복제가 아니므로 흐름 확인용.

## 환경 메모
- `pkill -f`로 프로세스를 죽일 때 자기 셸까지 죽는 경우가 있다 → `pgrep -f "[n]ursing_tts"` 처럼 대괄호 트릭을 쓴다.
- 백엔드 기본 포트 8765 (`NURSING_TTS_PORT`로 변경). 앱은 이미 떠 있는 **우리** 백엔드(`/api/health`가 `{"ok":true}`)만 재사용하고, 다른 프로그램이 8765를 쓰고 있으면 8766~으로 옮긴다. 렌더러는 `get-backend-url`로 실제 포트를 받는다.
- 앱 데이터 폴더(`userData/venv`)에 예전 빌드가 만든 Python 3.9 venv가 남아 있을 수 있다. `findPython`은 `pyvenv.cfg`로 3.10 미만을 걸러 "설치 안 됨"으로 취급한다 (마법사가 다시 만든다).
- Node 24에서 `npm ci` 뒤 `node_modules/electron/dist`만 있고 `path.txt`가 없으면(Electron 바이너리 추출이 조용히 중단됨) `~/Library/Caches/electron/*/electron-v*.zip`을 `ditto -x -k`로 `dist/`에 풀고 `path.txt`에 `Electron.app/Contents/MacOS/Electron`을 쓰면 된다.
