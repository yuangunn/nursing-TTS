import { useEffect, useState } from "react";
import { del, EngineInfo, get, put, Settings, UpdateInfo, UpdateSettings } from "../lib/api";
import Term from "../components/Term";
import SignalSelect from "../components/SignalSelect";
import InstallProgress from "../components/InstallProgress";

export default function SettingsPage() {
  const [s, setS] = useState<Settings | null>(null);
  const [engines, setEngines] = useState<EngineInfo[]>([]);
  const [apiKey, setApiKey] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [log, setLog] = useState("");
  const [backendDir, setBackendDir] = useState("");

  const load = async () => {
    try {
      setS(await get<Settings>("/api/settings"));
      setEngines((await get<{ engines: EngineInfo[] }>("/api/engines")).engines);
      setErr("");
    } catch (e) {
      setErr("백엔드에 연결할 수 없습니다: " + String(e));
    }
    if (window.nursing) {
      setLog(await window.nursing.getBackendLog());
      setBackendDir(await window.nursing.getBackendDir());
    }
  };
  useEffect(() => {
    load();
    window.nursing?.onBackendLog((line) => setLog((l) => (l + line).slice(-20000)));
  }, []);

  if (!s) {
    return (
      <div className="panel">
        {err ? <div className="error">{err}</div> : <div className="muted">불러오는 중…</div>}
        <div className="row" style={{ marginTop: 10 }}>
          <div className="narrow"><button onClick={async () => { await window.nursing?.restartBackend(); load(); }}>백엔드 재시작</button></div>
          <div className="narrow"><button onClick={load}>다시 시도</button></div>
        </div>
        <BackendHelp dir={backendDir} log={log} />
      </div>
    );
  }

  const save = async (patch: Partial<Settings>) => {
    setMsg("");
    try {
      const next = await put<Settings>("/api/settings", patch);
      setS(next);
      setEngines((await get<{ engines: EngineInfo[] }>("/api/engines")).engines);
      setMsg("저장됨");
      setTimeout(() => setMsg(""), 1500);
    } catch (e) {
      setErr(String(e));
    }
  };

  return (
    <div className="cols">
      <div>
        <div className="panel">
          <h2>TTS 엔진 <span className="hint">{msg}</span></h2>
          <label><input type="radio" name="eng" checked={s.tts_engine === "auto"} onChange={() => save({ tts_engine: "auto" })} /> 자동 (사용 가능한 복제 엔진 우선)</label>
          {engines.map((e) => (
            <div key={e.key} style={{ margin: "6px 0" }}>
              <label style={{ color: "inherit", fontSize: 13 }}>
                <input type="radio" name="eng" checked={s.tts_engine === e.key} onChange={() => save({ tts_engine: e.key })} /> {e.label}{" "}
                <span className={"badge " + (e.available ? "ok" : "bad")}>{e.available ? "사용 가능" : "사용 불가"}</span>
                {e.clones_voice && <span className="badge" style={{ marginLeft: 4 }}>목소리 복제</span>}
              </label>
              <div className="muted" style={{ marginLeft: 22 }}>{e.status}</div>
            </div>
          ))}
          <div className="row" style={{ marginTop: 10 }}>
            <div>
              <label>연산 장치</label>
              <select value={s.device} onChange={(e) => save({ device: e.target.value })}>
                <option value="auto">자동 (CUDA → MPS → CPU)</option>
                <option value="cuda">CUDA (NVIDIA GPU)</option>
                <option value="mps">MPS (Apple Silicon)</option>
                <option value="cpu">CPU (느림)</option>
              </select>
            </div>
            <div>
              <label>출력 샘플레이트</label>
              <select value={s.sample_rate} onChange={(e) => save({ sample_rate: Number(e.target.value) })}>
                <option value={24000}>24000 Hz (기본)</option>
                <option value={16000}>16000 Hz (STT 학습용)</option>
                <option value={44100}>44100 Hz</option>
              </select>
            </div>
          </div>
        </div>

        <div className="panel">
          <h2>Qwen3-TTS (내장 한국어 목소리 복제)</h2>
          <div className="muted" style={{ marginBottom: 8 }}>
            아래 "백엔드" 패널에서 <b>목소리 복제 엔진 포함</b>으로 설치하면 켜집니다. 모델(1.7B, 약 4.5 GB)은 설치 때 내려받습니다. GPU가 다른 PC에 있으면 이 엔진 대신 아래 HTTP 서버를 쓰세요.
          </div>
          <div className="row">
            <div>
              <label>모델 (Hugging Face ID 또는 로컬 경로)</label>
              <input type="text" value={s.qwen_model} onChange={(e) => setS({ ...s, qwen_model: e.target.value })} onBlur={() => save({ qwen_model: s.qwen_model })} />
            </div>
            <div className="narrow">
              <label>유휴 시 메모리 해제 (분, 0=유지)</label>
              <input type="number" value={s.qwen_idle_unload_min} min={0} max={120} onChange={(e) => save({ qwen_idle_unload_min: Number(e.target.value) })} />
            </div>
          </div>
        </div>

        <div className="panel">
          <h2>커스텀 HTTP TTS 서버</h2>
          <div className="muted" style={{ marginBottom: 6 }}>
            한국어 지원 복제 모델을 별도 환경에서 서버로 띄우고 연결합니다. 준비된 래퍼: <span className="kbd">scripts/servers/qwen3_tts_server.py</span> (Qwen3-TTS, Apache-2.0),{" "}
            <span className="kbd">chatterbox_server.py</span> (Chatterbox Multilingual, MIT), <span className="kbd">cosyvoice_server.py</span> (Fun-CosyVoice3). README의 "한국어 모델" 절 참고.
          </div>
          <input type="text" value={s.http_tts_url} onChange={(e) => setS({ ...s, http_tts_url: e.target.value })} onBlur={() => save({ http_tts_url: s.http_tts_url })} />
        </div>
      </div>

      <div>
        <div className="panel">
          <h2>저장 위치</h2>
          <div className="row">
            <div>
              <label>출력 폴더</label>
              <input type="text" value={s.output_dir} placeholder={s._output_dir_resolved} onChange={(e) => setS({ ...s, output_dir: e.target.value })} onBlur={() => save({ output_dir: s.output_dir })} />
            </div>
            <div className="narrow"><button onClick={async () => { const p = await window.nursing?.chooseDirectory(); if (p) save({ output_dir: p }); }}>선택…</button></div>
            <div className="narrow"><button onClick={() => window.nursing?.openPath(s._output_dir_resolved)}>열기</button></div>
          </div>
          <div className="muted">데이터 폴더(목소리·소음·설정): {s._data_dir}</div>
        </div>

        <div className="panel">
          <h2><Term k="LLM 다듬기" /> (<Term k="BYOK" />) <span className="hint">선택 사항 · 규칙 기반 생성 후 자연스럽게 재작성</span></h2>
          <div className="row">
            <div>
              <label>제공자</label>
              <select value={s.llm_provider} onChange={(e) => save({ llm_provider: e.target.value })}>
                <option value="none">사용 안 함</option>
                <option value="anthropic">Anthropic (Claude)</option>
                <option value="openai_compatible">OpenAI 호환 (OpenAI, Ollama, vLLM…)</option>
              </select>
            </div>
            <div>
              <label>모델</label>
              <input type="text" value={s.llm_model} placeholder={s.llm_provider === "anthropic" ? "claude-opus-5-5" : "gpt-4o-mini"} onChange={(e) => setS({ ...s, llm_model: e.target.value })} onBlur={() => save({ llm_model: s.llm_model })} />
            </div>
          </div>
          {s.llm_provider === "openai_compatible" && (
            <div className="row">
              <div>
                <label>Base URL</label>
                <input type="text" value={s.llm_base_url} placeholder="https://api.openai.com/v1 또는 http://localhost:11434/v1" onChange={(e) => setS({ ...s, llm_base_url: e.target.value })} onBlur={() => save({ llm_base_url: s.llm_base_url })} />
              </div>
            </div>
          )}
          <div className="row">
            <div>
              <label>API 키 {s.llm_api_key_set && <span className="badge ok">저장됨</span>}</label>
              <input type="password" value={apiKey} placeholder={s.llm_api_key_set ? "(저장된 키 유지 — 바꾸려면 입력)" : "sk-…"} onChange={(e) => setApiKey(e.target.value)} />
            </div>
            <div className="narrow"><button onClick={() => { if (apiKey) { save({ llm_api_key: apiKey }); setApiKey(""); } }}>키 저장</button></div>
            <div className="narrow"><button className="danger" onClick={async () => { await del("/api/settings/llm_api_key"); load(); }}>키 삭제</button></div>
          </div>
          <div className="muted">키는 이 PC의 설정 파일에만 저장되며 LLM 제공자에게만 전송됩니다. 환자명은 가명이지만, 외부 전송이 걱정되면 로컬 Ollama를 쓰세요.</div>
        </div>

        <div className="panel">
          <h2><Term k="ASR" /> 검증 (품질 게이트) <span className="hint">생성 직후 <Term k="Whisper" />로 되읽어 <Term k="CER" />이 높으면 표시</span></h2>
          <div className="muted" style={{ marginBottom: 6 }}>설치: <span className="kbd">pip install faster-whisper</span> (백엔드 venv). 합성이 대본과 다르게 나온 클립을 자동으로 걸러 학습 데이터 오염을 막습니다. 결과물 탭에서 개별 재검증도 가능합니다.</div>
          <div className="row">
            <div className="narrow">
              <label style={{ color: "inherit", fontSize: 13 }}><input type="checkbox" checked={s.asr_verify} onChange={(e) => save({ asr_verify: e.target.checked })} /> 생성 시 자동 검증</label>
            </div>
            <div>
              <label><Term k="Whisper" /> 모델</label>
              <select value={s.asr_model} onChange={(e) => save({ asr_model: e.target.value })}>
                {["tiny", "base", "small", "medium", "large-v3"].map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
            <div className="narrow">
              <label><Term k="CER" /> 기준</label>
              <input type="number" step={0.05} min={0.05} max={1} value={s.cer_threshold} onChange={(e) => save({ cer_threshold: Number(e.target.value) })} />
            </div>
            <div>
              <label>문장 재합성 <Term k="CER" /> 기준 (0~1)</label>
              <input type="number" step={0.05} min={0} max={1} value={s.chunk_cer_threshold ?? 0.3} title="합성 직후 문장마다 Whisper로 되읽어 이 값보다 CER이 높으면 그 문장만 새 시드로 다시 만듭니다" onChange={(e) => save({ chunk_cer_threshold: Number(e.target.value) })} />
            </div>
            <div>
              <label>문장 재합성 횟수 (0 = 끔)</label>
              <input type="number" step={1} min={0} max={5} value={s.chunk_retries ?? 2} onChange={(e) => save({ chunk_retries: Number(e.target.value) })} />
            </div>
          </div>
        </div>

        <div className="panel">
          <h2><Term k="시그널" /> 기본 형식</h2>
          <SignalSelect value={s.signal_format || "strict"} onChange={(v) => save({ signal_format: v || "strict" })} allowDefault={false} aliases={s.signal_aliases} onAliases={(v) => save({ signal_aliases: v })} />
          <div className="muted" style={{ marginTop: 6 }}>필수 형식은 「연도년 월월 일일 시간시 분분 환자명 님 기록종류 기록입니다」입니다. 다른 형식은 말투 관리 탭의 "시그널 형식"에서 추가할 수 있고, 파서가 날짜·시각·환자명·기록종류를 잡아내는지 예시 보기로 확인됩니다.</div>
        </div>

        <div className="panel">
          <h2>기본값</h2>
          <div className="row">
            <div>
              <label>기본 말투</label>
              <select value={s.default_style} onChange={(e) => save({ default_style: e.target.value })}>
                <option value="formal">격식체 위주</option>
                <option value="mixed">현장 혼합</option>
                <option value="casual">구어체 위주</option>
              </select>
            </div>
            <div>
              <label>기본 소음 크기</label>
              <input type="number" min={0} max={100} value={s.noise_default_level} onChange={(e) => save({ noise_default_level: Number(e.target.value) })} />
            </div>
            <div>
              <label>음성 음량 정규화 (<Term k="RMS" /> <Term k="dBFS" />)</label>
              <input type="number" step={1} min={-35} max={-10} value={s.loudness_dbfs} onChange={(e) => save({ loudness_dbfs: Number(e.target.value) })} />
            </div>
            <div>
              <label>바닥 소음 (<Term k="dBFS" />, 소음 꺼도 깔림)</label>
              <input type="number" step={1} min={-80} max={0} value={s.floor_dbfs ?? -56} title="말 사이 공백이 완전 무음이 되지 않게 깔리는 룸톤. 실제 녹음은 −52~−58. 0이면 없음" onChange={(e) => save({ floor_dbfs: Number(e.target.value) })} />
            </div>
            <div>
              <label>기본 울림 (0~0.3)</label>
              <input type="number" step={0.01} min={0} max={0.3} value={s.room_wet ?? 0.06} title="모든 녹음에 아주 약하게 적용되는 병실 울림. 소리 옵션의 '병실 울림'을 켜면 그쪽이 우선" onChange={(e) => save({ room_wet: Number(e.target.value) })} />
            </div>
            <div>
              <label>기본 구어 <Term k="흐트러짐" /> (0~3)</label>
              <input type="number" min={0} max={3} value={s.default_disfluency} onChange={(e) => save({ default_disfluency: Number(e.target.value) })} />
            </div>
          </div>
        </div>

        <div className="panel">
          <h2>회진 대화 소음 <span className="hint">등록 목소리로 읽은 뒤 역할마다 음높이(<Term k="반음" />)와 말속도(1 = 그 목소리 본래 속도)를 바꿉니다</span></h2>
          <div className="row">
            {(["doctor", "patient", "nurse"] as const).map((role) => (
              <div key={role}>
                <label>{{ doctor: "의사", patient: "환자", nurse: "다른 간호사" }[role]}</label>
                <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  <input type="number" step={0.5} min={-12} max={12} style={{ width: 70 }} title="반음 (−: 낮게, +: 높게)"
                    value={s.rounds_shift?.[role] ?? 0}
                    onChange={(e) => save({ rounds_shift: { ...s.rounds_shift, [role]: Number(e.target.value) } })} />
                  <span className="muted">반음</span>
                  <input type="number" step={0.05} min={0.6} max={1.6} style={{ width: 70 }} title="말속도 배율"
                    value={s.rounds_tempo?.[role] ?? 1}
                    onChange={(e) => save({ rounds_tempo: { ...s.rounds_tempo, [role]: Number(e.target.value) } })} />
                  <span className="muted">배속</span>
                </div>
              </div>
            ))}
            <div>
              <label>줄마다 속도 흔들기 (±)</label>
              <input type="number" step={0.01} min={0} max={0.3} value={s.rounds_tempo_jitter ?? 0.08} onChange={(e) => save({ rounds_tempo_jitter: Number(e.target.value) })} />
            </div>
          </div>
        </div>

        <BackendHelp dir={backendDir} log={log} />
        <UpdatePanel />
      </div>
    </div>
  );
}

function UpdatePanel() {
  const [us, setUs] = useState<UpdateSettings | null>(null);
  const [info, setInfo] = useState<UpdateInfo | null>(null);
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const load = () => window.nursing?.getUpdateSettings().then((s) => { setUs(s); if (s.lastResult) setInfo(s.lastResult); }).catch(() => undefined);
  useEffect(() => { load(); }, []);
  if (!window.nursing) return null;
  const check = async () => { setBusy(true); try { setInfo(await window.nursing!.checkUpdate(true)); await load(); } finally { setBusy(false); } };
  return (
    <div className="panel">
      <h2>업데이트 확인 <span className="hint">앱을 켤 때와 6시간마다 새 버전이 있는지 확인합니다</span>
        <span style={{ marginLeft: "auto", display: "flex", gap: 6 }}><button className="small" onClick={check} disabled={busy}>{busy ? "확인 중…" : "지금 확인"}</button></span>
      </h2>
      <div className="muted">
        {info ? (info.error ? <span className="badge warn">{info.error}</span>
          : info.newer ? <>새 버전 <b>v{info.latest}</b> 있음 (지금 v{info.current}) <button className="link" onClick={() => window.nursing?.openExternal(info.url)}>다운로드 페이지</button>{info.skipped && " · 이 버전은 알림 안 받음"}</>
          : <>최신 버전입니다 (v{info.current}{info.latest && info.latest !== info.current ? ` · 공개된 최신 v${info.latest}` : ""})</>)
          : "아직 확인하지 않았습니다"}
        {us?.lastCheck ? <> · 마지막 확인 {new Date(us.lastCheck).toLocaleString()}</> : null}
      </div>
      {us?.skipVersion && (
        <div className="row" style={{ marginTop: 6, alignItems: "center" }}>
          <div className="muted">알림 받지 않는 버전: v{us.skipVersion}</div>
          <div className="narrow"><button className="small" onClick={async () => { await window.nursing?.setUpdateSettings({ skipVersion: "" }); load(); }}>알림 다시 받기</button></div>
        </div>
      )}
      <div className="row" style={{ marginTop: 8 }}>
        <div>
          <label>GitHub 토큰 {us?.token && <span className="badge ok">저장됨</span>} <span className="hint">비공개 저장소의 릴리스를 읽으려면 필요 (repo 읽기 권한)</span></label>
          <input type="password" value={token} placeholder={us?.token ? "(저장된 토큰 유지 — 바꾸려면 입력)" : "ghp_…"} onChange={(e) => setToken(e.target.value)} />
        </div>
        <div className="narrow" style={{ alignSelf: "end" }}><button onClick={async () => { if (token) { await window.nursing?.setUpdateSettings({ token }); setToken(""); load(); } }}>토큰 저장</button></div>
        <div className="narrow" style={{ alignSelf: "end" }}><button className="danger" onClick={async () => { await window.nursing?.setUpdateSettings({ token: "" }); load(); }}>토큰 삭제</button></div>
      </div>
      <div className="row" style={{ marginTop: 6 }}>
        <div>
          <label>릴리스 목록 주소</label>
          <input type="text" value={us?.feedUrl || ""} onChange={(e) => setUs(us ? { ...us, feedUrl: e.target.value } : us)} onBlur={async () => { if (us) { await window.nursing?.setUpdateSettings({ feedUrl: us.feedUrl }); } }} />
        </div>
      </div>
    </div>
  );
}

function BackendHelp({ dir, log }: { dir: string; log: string }) {
  const [installed, setInstalled] = useState<boolean | null>(null);
  const [version, setVersion] = useState("");
  const [withQwen, setWithQwen] = useState(false);
  const [show, setShow] = useState(false);
  useEffect(() => {
    window.nursing?.backendInstalled().then(setInstalled).catch(() => setInstalled(null));
    window.nursing?.appVersion().then(setVersion).catch(() => undefined);
  }, [log]);
  return (
    <div className="panel">
      <h2>백엔드 {version && <span className="badge">앱 v{version}</span>}
        <span style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
          {installed !== null && <span className={"badge " + (installed ? "ok" : "warn")}>{installed ? "Python 환경 있음" : "Python 환경 없음"}</span>}
          <button className="small" onClick={async () => { await window.nursing?.restartBackend(); }}>백엔드 재시작</button>
          <button className="small" onClick={() => window.dispatchEvent(new CustomEvent("nursing:wizard"))}>처음 설정 다시 보기</button>
        </span>
      </h2>
      {window.nursing && (
        <>
          <div className="row" style={{ alignItems: "center" }}>
            <div className="narrow"><button className={show ? "" : "primary"} onClick={() => setShow((v) => !v)}>{installed ? "재설치 / 업데이트…" : "⬇ 백엔드 설치…"}</button></div>
            <div className="narrow">
              <label style={{ display: "inline-flex", gap: 6, alignItems: "center", color: "inherit", fontSize: 13, margin: 0 }}>
                <input type="checkbox" checked={withQwen} onChange={(e) => setWithQwen(e.target.checked)} /> 목소리 복제 엔진(Qwen3-TTS) 포함 <span className="badge warn">약 6.5 GB · 10~25분</span>
              </label>
            </div>
            <div className="muted">Python 3.10 이상 필요 (mac: <span className="kbd">brew install python</span>). 환경은 앱 데이터 폴더에 만들어집니다.</div>
          </div>
          {show && <InstallProgress key={withQwen ? "qwen" : "base"} withQwen={withQwen} />}
        </>
      )}
      <div className="muted" style={{ marginBottom: 6 }}>백엔드 폴더: {dir || "(브라우저 모드)"}{!window.nursing && <> · 개발 모드에서는 <span className="kbd">scripts/setup-backend.sh</span> (mac) / <span className="kbd">scripts\setup-backend.ps1</span> (Windows)</>}</div>
      <div className="log">{log || "(로그 없음)"}</div>
    </div>
  );
}
