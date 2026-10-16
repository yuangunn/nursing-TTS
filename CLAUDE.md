# 간호기록 음성 녹음 생성기 (nursing-TTS)

가상 환자의 간호기록을 체크박스로 고르면, 등록한 간호사 목소리로 읽어 주는 **녹음(wav) + 정답 텍스트(txt/json)** 를 만들어 STT 학습 데이터를 생산하는 데스크탑 앱. 모든 환자 정보는 가상/가명이다.

## 구조

| 경로 | 내용 |
|---|---|
| `backend/nursing_tts/` | Python 3.10+ FastAPI 백엔드. 대본 생성·발음 변환·TTS 어댑터·소음 합성·증강·검증·데이터셋 내보내기 |
| `backend/tests/` | pytest (36개). 무음 엔진으로 전체 파이프라인을 돈다 |
| `app/` | Electron 33 + React 18 + Vite 6 + TypeScript. `electron/main.ts`가 백엔드 프로세스와 설치기를 담당 |
| `scripts/` | `setup-backend.{sh,ps1}`, 한국어 복제 모델 래퍼 서버(`servers/qwen3_tts_server.py` 등) |
| `.github/workflows/` | `ci.yml` (pytest + typecheck/build), `release.yml` (`v*` 태그 또는 수동 실행 → mac dmg/zip, win exe를 prerelease에 업로드) |
| `docs/ROADMAP.md` | 마일스톤과 시작 프롬프트 |

### 백엔드 핵심 개념
- **두 가지 텍스트 층**: `spoken_text`(정답, 숫자·약어 그대로) vs `tts_text`(발음용, `korean.py`가 숫자/날짜/단위/약어를 한글로 풀어 씀). 정답 텍스트는 절대 발음형으로 저장하지 않는다.
- **시그널 라인**: 녹음 첫 줄은 반드시 `signal.py`의 형식 중 하나. 필수 형식은 「[연도]년 [월]월 [일]일 [시간]시 [분]분 [환자명] 님 [기록종류] 기록입니다」. 기록종류는 간호정보조사/퇴원간호/수술전설명/수술후설명/인계. `signal.parse()`가 어떤 변형이든 날짜·시각·이름·종류를 뽑아내야 한다.
- **템플릿**: `templates/s1_admission.py` … `s6_progress.py`는 선언형(`RecordTemplate/Section/Field/Option`). 연결형 문구는 `,`로 끝내고 `grammar.close_sentence()`가 종결형으로 바꾼다. 조사는 `grammar.fix_josa()`. 말투는 formal/casual/mixed/chart, `phrase_store.stylize()`가 플레이스홀더 치환 **후** 적용.
- **병동 시나리오 지식베이스**: `clinical.py`. 이 병동에 오는 수술(GS·OBGY·URO·ENT·OS·PS 30여 종)과 항암 regimen(유방·대장·췌장·자궁내막 14종)마다 개연성 있는 진단명·주 호소·현병력·나이/성별·재원 기간, 템플릿 필드 제한(`form`: 배액관 종류, 식이 단계, 소변줄, 장치, 추후 계획…)과 글 풀(`pools`: 통증 양상, 배액, 퇴원약, 수술/항암별 특이 교육…)을 적어 둔다. `fake.random_patient`는 여기서만 뽑고(`scenario=`로 강제 가능), `random_form`이 `_apply_scenario`로 폼을 좁힌다. 항암 입원은 `Patient.kind="chemo"`(regimen/cycle/day, POD 없음)로 S1·S4·S5·S6만 받고, 인트로는 `{treatment}`·`{stage}`(「POD 2」 또는 「항암 3차 D1」)를 쓴다. 병동 읽기 관행(사용자 확인): PICC는 "피아이씨씨"(픽 아님), "POD 3"은 "피오디 삼일째", "풀코드"라는 말은 쓰지 않는다(DNR/연명의료 서류가 있을 때만 말함). **새 수술/항암을 추가할 때는 clinical.py에 시나리오 하나를 넣고 `korean.py` 약어 읽기를 보강한다** (읽기는 2~5가지: 철자·한글 이름·혼합, `_SURGERY_READINGS`; 진단마다 맞는 주호소·현병력이 1개 이상 있어야 `coherent_pool` 테스트 통과; 퇴원 교육 `s4.special_edu`는 병동 퇴원 설명문 요약을 2~3개 뽑아 읽고, 퇴원간호는 퇴원 당일 오전 기록이라 "내일 퇴원" 문구 금지, 프로토콜 체크리스트 없음(교육만), 기본 말투는 격식체) (`tests/test_clinical.py`가 옵션 값·텍스트 필드 존재와 대본 잔여 영문을 검사).
- **프로토콜 체크리스트**: `templates/protocols.py` (정규 차팅: Routine, 낙상, 통증, Wound, 약물, 호흡, 배액관, 도뇨관, 고체온, 오심, 혈당 …). `Section.group == "protocol"`, 필드 키는 `p_` 접두.
- **말투 변형 관리**: `extra_phrases.py`(내장) + `phrase_store.py`(사용자 오버라이드 → `data_dir/phrases.json`). UI "말투 관리" 탭.
- **참조 샘플 선택**: `voices.pick_reference(style=)`가 S1(간호정보조사)에는 질문형 전사 클립을, 나머지에는 서술형 클립을 우선 고른다(복제가 참조 억양을 따라가기 때문). 샘플 전사가 틀리면 복제 말투가 흔들리므로 새 목소리를 등록하면 `scripts/recheck_samples.py`로 전사를 한 번 확인한다.
- **TTS 어댑터**: `tts/{qwen,http_engine,system,silent}.py`, `tts/registry.py`. `auto`는 qwen → http → system → silent. `qwen`은 Qwen3-TTS 1.7B 내장 복제(참조 프롬프트 캐시, 유휴 시 언로드, `synthesize_many`로 문장 조각을 `qwen_batch`개씩 한 번에 생성), `http`는 원격 GPU 등 외부 서버용. 결과 json의 `timing`에 합성/믹스/검증/전체 소요 초가 남는다. HTTP 어댑터는 `scripts/servers/_common.py` 규약(`POST /synthesize`). `tts/base.py`의 `synthesize_paragraphs`는 문단을 **문장 단위**(20자 미만은 이웃과 합침)로 합성하고, 문장 사이 쉼은 실제 간호사 녹음에 맞춘 로그정규 분포(중앙값 0.6초, p90 1.6초, 문단 바뀔 때 ×1.6)로 넣는다.
- **오디오**: `audio/noise.py`(합성 소음 카탈로그), `mixer.py`(SNR; 소음을 꺼도 항상 설정 `floor_dbfs` 룸톤 바닥과 `room_wet` 약한 울림을 깐다. 사용자 피드백: 무음 공백의 볼륨 갭), `augment.py`(채널 프리셋·속도), `disfluency.py`(간투사·숫자 정정), `slicer.py`(긴 녹음 → 6~14초 조각), `verify.py`(faster-whisper CER: 정답/발음/「전사를 발음 변환한 것」 세 기준 중 최소); 검증이 켜져 있으면 합성 직후 문장 조각마다 되읽어 `chunk_cer_threshold`(0.3) 초과 조각만 새 시드로 `chunk_retries`(2)회 다시 합성하고 json `segments[].cer/retries`·`chunk_verify`에 남김, `dataset.py`(LJSpeech/NeMo/Whisper 내보내기). `rounds.py`는 의사·환자·간호사 회진 대화를 등록된 목소리(복제 엔진)로 읽고 역할별 음높이·말속도를 바꿔(설정 `rounds_shift` 기본 의사 −4·환자 −1·간호사 +3반음, `rounds_tempo` 1.05·0.9·1.15배, 줄마다 ±`rounds_tempo_jitter`; librosa pitch_shift/time_stretch, librosa는 qwen-tts 의존성) 멀리서 들리는 "내 소음" 클립으로 저장(`POST /api/noises/rounds`, 소리 옵션의 "회진 대화 만들기" 버튼, 설정 탭 "회진 대화 소음"). 복제 엔진이 없으면 시스템 TTS 폴백. 실제 소음 녹음(유튜브에서 딴 네뷸라이저·중환자실·모니터 알람 등)은 저작권 때문에 저장소에 넣지 않고 `backend/local_data/noise/`와 사용자 데이터 폴더(`noises/`)에만 둔다.
- **파일명**: `{YYYYMMDD_HHMM}_{환자명}.wav/.txt/.json`. 데이터 폴더는 `NURSING_TTS_DATA` 환경변수 또는 OS 앱 데이터 폴더. json의 `segments`는 문장 조각마다 `{start, end, text(정답), tts}`로, 내보내기 `max_clip_sec`(기본 30)이 이 경계에서 긴 녹음을 `_p01…` 조각으로 자른다(Whisper 30초 창). `scripts/check_export.py`로 내보낸 폴더를 검사한다.

### 앱 핵심 개념
- `electron/main.ts`: 백엔드 Python 탐색(`userData/venv` → `backend/.venv`), 설치기(`setupBackend`: venv 생성 → pip → requirements → (Qwen: torch → requirements-qwen → 모델 다운로드) → 시작, `setup-progress` 이벤트로 단계/퍼센트/ETA 전송, 3.10 미만 venv 재생성, pip 되감기 감지 중단), `check-environment`.
- `src/App.tsx`: 처음 설정 마법사(`SetupWizard`) → 작업 순서 사이드바(`Sidebar`: 1 목소리 → 2 녹음 → 3 대량 → 4 결과물) + 시작 가이드(`GettingStarted`). 온보딩 완료 여부는 `localStorage`(`lib/onboarding.ts`).
- 페이지: `RecordPage`(1~7 단계), `VoicesPage`, `BatchPage`, `ResultsPage`, `PhrasesPage`, `SettingsPage`. 백엔드 호출은 `lib/api.ts` 하나로. 목소리 선택의 "샘플 듣기"는 `lib/voiceDemo.ts` → `GET /api/voices/{id}/demo`(고정 문장 합성, 캐시). 원음 샘플은 목소리 관리 화면에서만 재생한다.

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
- 무작위 폼의 필드 간 모순은 `fake._consistency`가 막는다(PCA인데 통증 0, 소변줄 없는데 도뇨관 프로토콜, 퇴원 기록에 PCA 등). `tests/test_script_quality.py`가 210개 대본에서 금지 패턴을 검사하므로 새 필드·프로토콜을 넣으면 거기에도 걸리는지 본다. 말투는 실제 병동 호칭을 따른다: OOO 교수님, 환자분, 보호자분(사용자 지적 2026-10-15).
- 새 체크 항목/필드를 추가하면 (1) 템플릿 선언, (2) `extra_phrases.py` 변형 2~5개, (3) `fake.py` 무작위 생성 풀, (4) 필요하면 `korean.py` 약어 읽기까지 한 세트로.
- 실제 환자 데이터는 절대 저장소에 넣지 않는다. 테스트 녹음은 `local_data/`(gitignore).
- 목소리 다양화는 **공개 데이터 화자 가져오기**(`scripts/import_public_voices.py`, Zeroth-Korean CC BY 4.0)로 한다. 커뮤니티 RVC .pth(출처·동의 불명) 같은 음성 변조 모델은 쓰지 않는다(사용자 결정 2026-10-15). 가져온 목소리는 메모에 「출처: …」가 남고 내보내기 README에 자동으로 표기된다.

## 알려진 제한 / 다음 할 일
- F5-TTS는 제거했다(기본 vocab에 한글 없음, 공개 한국어 체크포인트 없음). 내장 복제는 Qwen3-TTS 1.7B(M4 MPS에서 RTF 약 2.3), 1.7B vs 0.6B 품질 비교와 실제 간호사 녹음 청취 검증은 `docs/ROADMAP.md` M1 참고.
- 코드 서명/공증 없음. 첫 실행 시 우클릭 → 열기 또는 `xattr -dr com.apple.quarantine`.
- 시스템 TTS(macOS `say`)는 복제가 아니므로 흐름 확인용.

## 환경 메모
- `pkill -f`로 프로세스를 죽일 때 자기 셸까지 죽는 경우가 있다 → `pgrep -f "[n]ursing_tts"` 처럼 대괄호 트릭을 쓴다.
- 백엔드 기본 포트 8765 (`NURSING_TTS_PORT`로 변경). 앱은 이미 떠 있는 **우리** 백엔드(`/api/health`가 `{"ok":true}`)만 재사용하고, 다른 프로그램이 8765를 쓰고 있으면 8766~으로 옮긴다. 렌더러는 `get-backend-url`로 실제 포트를 받는다.
- 앱 데이터 폴더(`userData/venv`)에 예전 빌드가 만든 Python 3.9 venv가 남아 있을 수 있다. `findPython`은 `pyvenv.cfg`로 3.10 미만을 걸러 "설치 안 됨"으로 취급한다 (마법사가 다시 만든다).
- Node 24에서 `npm ci` 뒤 `node_modules/electron/dist`만 있고 `path.txt`가 없으면(Electron 바이너리 추출이 조용히 중단됨) `~/Library/Caches/electron/*/electron-v*.zip`을 `ditto -x -k`로 `dist/`에 풀고 `path.txt`에 `Electron.app/Contents/MacOS/Electron`을 쓰면 된다.
