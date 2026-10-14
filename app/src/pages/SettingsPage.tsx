import { useEffect, useState } from "react";
import { del, EngineInfo, get, put, Settings } from "../lib/api";
import SignalSelect from "../components/SignalSelect";

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

  const chooseFile = async (key: "f5_ckpt_file" | "f5_vocab_file") => {
    const p = await window.nursing?.chooseFile(key === "f5_ckpt_file" ? [{ name: "Checkpoint", extensions: ["pt", "safetensors", "bin"] }] : [{ name: "Vocab", extensions: ["txt"] }]);
    if (p) save({ [key]: p } as Partial<Settings>);
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
          <h2>F5-TTS (로컬 목소리 복제)</h2>
          <div className="muted" style={{ marginBottom: 8 }}>
            설치: <span className="kbd">pip install -r backend/requirements-f5.txt</span>. 기본 체크포인트는 영어/중국어용이므로 <b>한국어 파인튜닝 체크포인트</b>를 지정하세요 (README 참고).
          </div>
          <div className="row">
            <div>
              <label>모델 이름</label>
              <input type="text" value={s.f5_model} onChange={(e) => setS({ ...s, f5_model: e.target.value })} onBlur={() => save({ f5_model: s.f5_model })} />
            </div>
            <div className="narrow">
              <label>NFE step (품질↔속도)</label>
              <input type="number" value={s.f5_nfe_step} min={8} max={64} onChange={(e) => save({ f5_nfe_step: Number(e.target.value) })} />
            </div>
            <div className="narrow">
              <label>속도</label>
              <input type="number" value={s.f5_speed} min={0.6} max={1.5} step={0.05} onChange={(e) => save({ f5_speed: Number(e.target.value) })} />
            </div>
          </div>
          <div className="row">
            <div>
              <label>한국어 체크포인트 (.pt / .safetensors)</label>
              <input type="text" value={s.f5_ckpt_file} onChange={(e) => setS({ ...s, f5_ckpt_file: e.target.value })} onBlur={() => save({ f5_ckpt_file: s.f5_ckpt_file })} />
            </div>
            <div className="narrow"><button onClick={() => chooseFile("f5_ckpt_file")}>찾기…</button></div>
          </div>
          <div className="row">
            <div>
              <label>vocab.txt</label>
              <input type="text" value={s.f5_vocab_file} onChange={(e) => setS({ ...s, f5_vocab_file: e.target.value })} onBlur={() => save({ f5_vocab_file: s.f5_vocab_file })} />
            </div>
            <div className="narrow"><button onClick={() => chooseFile("f5_vocab_file")}>찾기…</button></div>
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
          <h2>LLM 다듬기 (BYOK) <span className="hint">선택 사항 · 규칙 기반 생성 후 자연스럽게 재작성</span></h2>
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
          <h2>ASR 검증 (품질 게이트) <span className="hint">생성 직후 Whisper로 되읽어 CER이 높으면 표시</span></h2>
          <div className="muted" style={{ marginBottom: 6 }}>설치: <span className="kbd">pip install faster-whisper</span> (백엔드 venv). 합성이 대본과 다르게 나온 클립을 자동으로 걸러 학습 데이터 오염을 막습니다. 결과물 탭에서 개별 재검증도 가능합니다.</div>
          <div className="row">
            <div className="narrow">
              <label style={{ color: "inherit", fontSize: 13 }}><input type="checkbox" checked={s.asr_verify} onChange={(e) => save({ asr_verify: e.target.checked })} /> 생성 시 자동 검증</label>
            </div>
            <div>
              <label>Whisper 모델</label>
              <select value={s.asr_model} onChange={(e) => save({ asr_model: e.target.value })}>
                {["tiny", "base", "small", "medium", "large-v3"].map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
            <div className="narrow">
              <label>CER 기준</label>
              <input type="number" step={0.05} min={0.05} max={1} value={s.cer_threshold} onChange={(e) => save({ cer_threshold: Number(e.target.value) })} />
            </div>
          </div>
        </div>

        <div className="panel">
          <h2>시그널 기본 형식</h2>
          <SignalSelect value={s.signal_format || "strict"} onChange={(v) => save({ signal_format: v || "strict" })} allowDefault={false} aliases={s.signal_aliases} onAliases={(v) => save({ signal_aliases: v })} />
          <div className="muted" style={{ marginTop: 6 }}>필수 형식은 「연도년 월월 일일 시간시 분분 환자명 님 기록종류 기록입니다」입니다. 다른 형식은 말투 관리 탭의 "시그널 형식"에서 추가할 수 있고, 파서가 날짜·시각·환자명·기록종류를 잡아내는지 예시 보기로 확인됩니다.</div>
        </div>

        <div className="panel">
          <h2>기본값</h2>
          <div className="row">
            <div>
              <label>기본 말투</label>
              <select value={s.default_style} onChange={(e) => save({ default_style: e.target.value })}>
                <option value="mixed">현장 혼합</option>
                <option value="casual">구어체 위주</option>
                <option value="formal">격식체 위주</option>
              </select>
            </div>
            <div>
              <label>기본 소음 크기</label>
              <input type="number" min={0} max={100} value={s.noise_default_level} onChange={(e) => save({ noise_default_level: Number(e.target.value) })} />
            </div>
            <div>
              <label>음성 음량 정규화 (RMS dBFS)</label>
              <input type="number" step={1} min={-35} max={-10} value={s.loudness_dbfs} onChange={(e) => save({ loudness_dbfs: Number(e.target.value) })} />
            </div>
            <div>
              <label>기본 구어 흐트러짐 (0~3)</label>
              <input type="number" min={0} max={3} value={s.default_disfluency} onChange={(e) => save({ default_disfluency: Number(e.target.value) })} />
            </div>
          </div>
        </div>

        <BackendHelp dir={backendDir} log={log} />
      </div>
    </div>
  );
}

function BackendHelp({ dir, log }: { dir: string; log: string }) {
  const [installed, setInstalled] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState("");
  const [version, setVersion] = useState("");
  useEffect(() => {
    window.nursing?.backendInstalled().then(setInstalled).catch(() => setInstalled(null));
    window.nursing?.appVersion().then(setVersion).catch(() => undefined);
  }, [log]);
  const setup = async (f5: boolean) => {
    if (!window.nursing) return;
    setBusy(true);
    setResult("설치 중… (수 분 소요, 아래 로그 참고)");
    try {
      const r = await window.nursing.setupBackend(f5);
      setResult(r.message);
      setInstalled(r.ok);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="panel">
      <h2>백엔드 {version && <span className="badge">앱 v{version}</span>}
        <span style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
          {installed !== null && <span className={"badge " + (installed ? "ok" : "warn")}>{installed ? "Python 환경 있음" : "Python 환경 없음"}</span>}
          <button className="small" onClick={async () => { await window.nursing?.restartBackend(); }}>백엔드 재시작</button>
        </span>
      </h2>
      {window.nursing && (
        <div className="row">
          <div className="narrow"><button className="primary" disabled={busy} onClick={() => setup(false)}>{installed ? "백엔드 재설치/업데이트" : "⬇ 백엔드 설치 (처음 한 번)"}</button></div>
          <div className="narrow"><button disabled={busy} onClick={() => setup(true)} title="PyTorch + F5-TTS까지 설치 (수 GB)">+ F5-TTS 포함 설치</button></div>
          <div className="muted">Python 3.10 이상이 PC에 있어야 합니다 (mac: <span className="kbd">brew install python</span>). 환경은 앱 데이터 폴더에 만들어집니다.{result && <> · {result}</>}</div>
        </div>
      )}
      <div className="muted" style={{ marginBottom: 6 }}>백엔드 폴더: {dir || "(브라우저 모드)"}{!window.nursing && <> · 개발 모드에서는 <span className="kbd">scripts/setup-backend.sh</span> (mac) / <span className="kbd">scripts\setup-backend.ps1</span> (Windows)</>}</div>
      <div className="log">{log || "(로그 없음)"}</div>
    </div>
  );
}
