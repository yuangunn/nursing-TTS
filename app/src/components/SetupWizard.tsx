import { useEffect, useState } from "react";
import { EngineInfo, EnrollScript, EnvInfo, get, post, put, Settings, Voice } from "../lib/api";
import { AppStatus, setOnboarded } from "../lib/onboarding";
import { Recorder, startRecording } from "../lib/wav";
import InstallProgress from "./InstallProgress";

/**
 * First-run wizard. Full screen until the user finishes (or skips) it.
 * 1 환영 → 2 환경 점검 → 3 백엔드 설치 → 4 음성 엔진 → 5 첫 목소리 → 6 완료
 */
interface Props {
  status: AppStatus;
  refresh: () => Promise<void>;
  onFinish: (goto: "record" | "voices") => void;
}

type Step = 0 | 1 | 2 | 3 | 4 | 5;
const STEPS = ["시작", "환경 점검", "백엔드 설치", "음성 엔진", "첫 목소리", "완료"];

export default function SetupWizard({ status, refresh, onFinish }: Props) {
  const [step, setStep] = useState<Step>(0);
  const [env, setEnv] = useState<EnvInfo | null>(null);
  const [envBusy, setEnvBusy] = useState(false);
  const [withQwen, setWithQwen] = useState(false);
  const electron = !!window.nursing;

  const checkEnv = async () => {
    if (!window.nursing) return;
    setEnvBusy(true);
    try { setEnv(await window.nursing.checkEnvironment()); } finally { setEnvBusy(false); }
  };
  useEffect(() => { if (step === 1) checkEnv(); }, [step]);

  const next = () => setStep((s) => Math.min(5, s + 1) as Step);
  const back = () => setStep((s) => Math.max(0, s - 1) as Step);
  const finish = (goto: "record" | "voices") => { setOnboarded(true); onFinish(goto); };

  const installed = status.backendOk || env?.backendRunning;

  return (
    <div className="wizard">
      <div className="wizard-card">
        <div className="wizard-side">
          <div className="brand"><div className="logo" /><div><h1>간호기록 음성 녹음 생성기</h1><small>처음 설정</small></div></div>
          <ol className="wizard-steps">
            {STEPS.map((s, i) => (
              <li key={s} className={i === step ? "cur" : i < step ? "done" : ""}><span>{i < step ? "✓" : i + 1}</span>{s}</li>
            ))}
          </ol>
          <div className="muted" style={{ marginTop: "auto" }}>언제든 설정 탭 → "처음 설정 다시 보기"로 돌아올 수 있습니다.</div>
        </div>

        <div className="wizard-main">
          {step === 0 && (
            <>
              <h2>반갑습니다 👋</h2>
              <p className="lead">이 앱은 <b>가상 환자의 간호기록</b>을 체크박스로 고르면, 등록한 간호사 목소리로 읽어 주는 <b>녹음 파일과 정답 텍스트</b>를 만들어 줍니다. 음성 인식(STT) 학습 데이터를 만들기 위한 도구입니다.</p>
              <div className="flow">
                <div><b>1</b><span>목소리 등록</span><small>간호사 목소리를 10초씩 몇 개 녹음</small></div>
                <div className="arr">→</div>
                <div><b>2</b><span>환자 상태 체크</span><small>기록 종류와 상태를 체크박스로 선택</small></div>
                <div className="arr">→</div>
                <div><b>3</b><span>녹음 생성</span><small>병동 소음까지 섞은 wav + txt 저장</small></div>
              </div>
              <p className="muted">처음 설정은 약 5분 걸립니다. 그중 대부분은 백엔드(음성 처리 엔진) 설치 시간입니다.</p>
              <div className="wizard-actions"><button className="primary big" onClick={next}>시작하기 →</button><button className="ghost" onClick={() => finish("record")}>건너뛰고 바로 둘러보기</button></div>
            </>
          )}

          {step === 1 && (
            <>
              <h2>환경 점검</h2>
              <p className="lead">설치 전에 이 PC에 필요한 것이 있는지 확인합니다.</p>
              {!electron ? (
                <div className="callout">브라우저(개발) 모드입니다. 백엔드를 터미널에서 직접 실행한 뒤 다음으로 넘어가세요.</div>
              ) : (
                <ul className="checklist">
                  <Check ok={env ? env.python.ok : null} busy={envBusy} label="Python 3.10 이상"
                    detail={env ? (env.python.ok ? `Python ${env.python.version} (${env.python.path})` : env.python.found ? `Python ${env.python.version}은 너무 낮습니다` : "Python을 찾지 못했습니다") : "확인 중…"}
                    fix={env && !env.python.ok ? (
                      <div className="fixbox">
                        {env.platform === "darwin" ? (
                          <>
                            <div>Homebrew가 있다면 터미널에서: <span className="kbd">brew install python</span></div>
                            <div>또는 python.org에서 설치 파일을 받으세요 (macOS 64-bit universal installer).</div>
                            <div className="row" style={{ marginTop: 6 }}>
                              <div className="narrow"><button className="small" onClick={() => window.nursing?.openExternal("https://www.python.org/downloads/macos/")}>python.org 열기</button></div>
                              <div className="narrow"><button className="small" onClick={() => navigator.clipboard.writeText("brew install python")}>brew 명령 복사</button></div>
                            </div>
                          </>
                        ) : (
                          <>
                            <div>python.org에서 설치 파일을 받아 실행하고, 설치 화면에서 <b>"Add python.exe to PATH"</b>를 꼭 체크하세요.</div>
                            <div className="row" style={{ marginTop: 6 }}><div className="narrow"><button className="small" onClick={() => window.nursing?.openExternal("https://www.python.org/downloads/windows/")}>python.org 열기</button></div></div>
                          </>
                        )}
                        <div className="muted" style={{ marginTop: 6 }}>설치가 끝나면 "다시 확인"을 누르세요.</div>
                      </div>
                    ) : null} />
                  <Check ok={env ? (env.diskFreeGb === null ? null : env.diskFreeGb >= (withQwen ? 10 : 1)) : null} busy={envBusy} label="디스크 여유 공간"
                    detail={env ? (env.diskFreeGb === null ? "확인 불가" : `${env.diskFreeGb} GB 여유 (기본 설치 약 0.3 GB, 목소리 복제 엔진 포함 시 약 6.5 GB)`) : "확인 중…"} />
                  <Check ok={env ? env.backendInstalled : null} busy={envBusy} label="백엔드 Python 환경" neutral
                    detail={env ? (env.backendInstalled ? `이미 설치됨 (${env.venvDir})` : "아직 없음 — 다음 단계에서 설치합니다") : "확인 중…"} />
                  <Check ok={env ? env.backendRunning : null} busy={envBusy} label="백엔드 실행 상태" neutral
                    detail={env ? (env.backendRunning ? "실행 중" : "꺼져 있음 — 설치 후 자동으로 켜집니다") : "확인 중…"} />
                </ul>
              )}
              <div className="wizard-actions">
                <button onClick={back}>← 이전</button>
                {electron && <button onClick={checkEnv} disabled={envBusy}>다시 확인</button>}
                <button className="primary" onClick={next} disabled={electron && !!env && !env.python.ok && !env.backendInstalled}>다음 →</button>
              </div>
            </>
          )}

          {step === 2 && (
            <>
              <h2>백엔드 설치</h2>
              {installed && !withQwen ? (
                <>
                  <div className="callout ok">백엔드가 이미 설치되어 실행 중입니다. 이 단계는 건너뛰어도 됩니다.</div>
                  <p className="muted">목소리 복제 엔진(Qwen3-TTS)을 지금 같이 설치하려면 아래를 켜고 설치를 시작하세요. 나중에 설정 탭에서도 할 수 있습니다.</p>
                </>
              ) : (
                <p className="lead">음성 처리를 담당하는 Python 백엔드를 이 PC에 설치합니다. 앱 데이터 폴더에만 설치되고, 삭제하면 깨끗이 지워집니다.</p>
              )}
              <label className="opt">
                <input type="checkbox" checked={withQwen} onChange={(e) => setWithQwen(e.target.checked)} />
                <span><b>Qwen3-TTS 목소리 복제 엔진도 설치</b> <span className="badge warn">약 6.5 GB · 10~25분</span><br /><small className="muted">등록한 간호사 목소리로 한국어를 합성하려면 필요합니다. Apple Silicon 또는 NVIDIA GPU에서 실시간의 약 2배 시간이 걸리고, CPU만 있으면 매우 느립니다. 급하면 끄고 시스템 음성으로 흐름을 먼저 확인해도 됩니다.</small></span>
              </label>
              {(!installed || withQwen) && <InstallProgress key={withQwen ? "qwen" : "base"} withQwen={withQwen} onDone={async (ok) => { if (ok) await refresh(); }} />}
              <div className="wizard-actions">
                <button onClick={back}>← 이전</button>
                <button className="primary" onClick={next} disabled={!installed && electron}>다음 →</button>
                {!installed && electron && <span className="muted">설치가 끝나면 다음으로 넘어갈 수 있습니다.</span>}
              </div>
            </>
          )}

          {step === 3 && <EngineStep onBack={back} onNext={next} />}

          {step === 4 && <VoiceStep onBack={back} onNext={next} onSkip={next} refresh={refresh} />}

          {step === 5 && (
            <>
              <h2>준비가 끝났습니다 🎉</h2>
              <p className="lead">이제 녹음을 만들 수 있습니다. 왼쪽 메뉴는 작업 순서대로 번호가 붙어 있고, 첫 화면의 <b>시작 가이드</b>가 다음에 할 일을 알려 줍니다.</p>
              <ul className="summary">
                <li><span className={"dot " + (status.backendOk ? "ok" : "bad")} /> 백엔드 {status.backendOk ? "실행 중" : "꺼짐"} · 엔진: {status.engineLabel || "—"}</li>
                <li><span className={"dot " + (status.voices ? "ok" : "")} /> 등록된 목소리 {status.voices}개{status.voices ? "" : " — 목소리 없이도 시스템 음성으로 체험할 수 있습니다"}</li>
              </ul>
              <div className="wizard-actions">
                <button className="primary big" onClick={() => finish("record")}>첫 녹음 만들러 가기 →</button>
                {!status.voices && <button onClick={() => finish("voices")}>먼저 목소리 등록하기</button>}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Check({ ok, busy, label, detail, fix, neutral }: { ok: boolean | null; busy: boolean; label: string; detail: string; fix?: React.ReactNode; neutral?: boolean }) {
  const cls = busy || ok === null ? "wait" : ok ? "ok" : neutral ? "info" : "bad";
  return (
    <li className={cls}>
      <span className="ico">{cls === "ok" ? "✓" : cls === "bad" ? "✕" : cls === "info" ? "·" : "…"}</span>
      <div style={{ flex: 1 }}>
        <div className="lbl">{label}</div>
        <div className="muted">{detail}</div>
        {fix}
      </div>
    </li>
  );
}

function EngineStep({ onBack, onNext }: { onBack: () => void; onNext: () => void }) {
  const [engines, setEngines] = useState<EngineInfo[]>([]);
  const [sel, setSel] = useState("");
  const [err, setErr] = useState("");
  const load = async () => {
    try {
      const e = await get<{ selected: string; engines: EngineInfo[] }>("/api/engines");
      setEngines(e.engines);
      setSel(e.selected);
      setErr("");
    } catch (ex) { setErr("백엔드에 연결되지 않아 엔진 목록을 불러올 수 없습니다. 이전 단계에서 설치/시작을 확인하세요."); }
  };
  useEffect(() => { load(); }, []);
  const choose = async (key: string) => {
    setSel(key);
    try { await put<Settings>("/api/settings", { tts_engine: key }); } catch (e) { setErr(String(e)); }
  };
  const desc: Record<string, string> = {
    auto: "사용 가능한 복제 엔진이 있으면 쓰고, 없으면 시스템 음성으로 대신합니다.",
    qwen: "내장 한국어 목소리 복제 (Qwen3-TTS 1.7B). 설치되어 있으면 '자동'이 이 엔진을 씁니다.",
    http: "별도로 띄운 TTS 서버(Qwen3-TTS, CosyVoice 등)에 연결합니다. 고급 사용자용.",
    system: "이 PC의 기본 음성(macOS say / Windows SAPI). 복제는 아니지만 전체 흐름을 바로 확인할 수 있습니다.",
    silent: "소리 없는 더미 wav. 대본·파일 생성만 테스트할 때.",
  };
  return (
    <>
      <h2>음성 엔진 선택</h2>
      <p className="lead">녹음을 어떤 음성으로 만들지 고릅니다. <b>처음에는 "자동"</b>을 두면 됩니다. 복제 엔진이 없으면 시스템 음성으로 흐름을 먼저 확인하고, 나중에 설정 탭에서 바꿀 수 있습니다.</p>
      {err && <div className="error">{err}</div>}
      <div className="engine-list">
        <label className={"engine" + (sel === "auto" ? " on" : "")}>
          <input type="radio" name="eng" checked={sel === "auto"} onChange={() => choose("auto")} />
          <div><b>자동 (권장)</b><div className="muted">{desc.auto}</div></div>
        </label>
        {engines.map((e) => (
          <label key={e.key} className={"engine" + (sel === e.key ? " on" : "") + (e.available ? "" : " off")}>
            <input type="radio" name="eng" checked={sel === e.key} onChange={() => choose(e.key)} />
            <div>
              <b>{e.label}</b> <span className={"badge " + (e.available ? "ok" : "bad")}>{e.available ? "사용 가능" : "사용 불가"}</span>{e.clones_voice && <span className="badge" style={{ marginLeft: 4 }}>목소리 복제</span>}
              <div className="muted">{desc[e.key] || e.status}</div>
              {!e.available && <div className="muted" style={{ opacity: 0.8 }}>{e.status}</div>}
            </div>
          </label>
        ))}
      </div>
      <div className="wizard-actions"><button onClick={onBack}>← 이전</button><button className="primary" onClick={onNext}>다음 →</button></div>
    </>
  );
}

function VoiceStep({ onBack, onNext, onSkip, refresh }: { onBack: () => void; onNext: () => void; onSkip: () => void; refresh: () => Promise<void> }) {
  const [name, setName] = useState("간호사 A");
  const [voice, setVoice] = useState<Voice | null>(null);
  const [scripts, setScripts] = useState<EnrollScript[]>([]);
  const [idx, setIdx] = useState(0);
  const [recorder, setRecorder] = useState<Recorder | null>(null);
  const [level, setLevel] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  const [micOk, setMicOk] = useState<boolean | null>(null);
  const [timer, setTimer] = useState<number | null>(null);

  useEffect(() => {
    get<EnrollScript[]>("/api/enroll-scripts").then(setScripts).catch(() => undefined);
    get<Voice[]>("/api/voices").then((vs) => { if (vs.length) { setVoice(vs[0]); setName(vs[0].name); } }).catch(() => undefined);
    navigator.mediaDevices?.getUserMedia({ audio: true }).then((s) => { s.getTracks().forEach((t) => t.stop()); setMicOk(true); }).catch(() => setMicOk(false));
  }, []);

  const ensureVoice = async (): Promise<Voice | null> => {
    if (voice) return voice;
    if (!name.trim()) { setErr("목소리 이름을 입력하세요."); return null; }
    const v = await post<Voice>("/api/voices", { name: name.trim(), note: "처음 설정에서 등록" });
    setVoice(v);
    return v;
  };
  const script = scripts[idx];
  const record = async () => {
    setErr("");
    try {
      const v = await ensureVoice();
      if (!v) return;
      const r = await startRecording((lv) => setLevel(lv));
      setRecorder(r); setElapsed(0);
      const start = Date.now();
      setTimer(window.setInterval(() => setElapsed((Date.now() - start) / 1000), 100));
    } catch (e) { setErr("마이크를 사용할 수 없습니다: " + String(e)); }
  };
  const stop = async () => {
    if (!recorder || !voice) return;
    if (timer) window.clearInterval(timer);
    const blob = await recorder.stop();
    setRecorder(null);
    setBusy("샘플 저장 중…");
    try {
      const fd = new FormData();
      fd.append("file", blob, "recording.wav");
      fd.append("transcript", script?.text || "");
      fd.append("script_id", script?.id || "");
      const { apiUrl } = await import("../lib/api");
      const r = await fetch(apiUrl(`/api/voices/${voice.id}/samples`), { method: "POST", body: fd });
      if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
      const vs = await get<Voice[]>("/api/voices");
      setVoice(vs.find((x) => x.id === voice.id) || voice);
      setIdx((i) => Math.min(scripts.length - 1, i + 1));
      await refresh();
    } catch (e) { setErr(String(e)); } finally { setBusy(""); }
  };
  const n = voice?.samples.length || 0;

  return (
    <>
      <h2>첫 목소리 등록 <span className="badge">선택 사항</span></h2>
      <p className="lead">간호사 목소리를 복제하려면 <b>10초짜리 샘플 3개</b> 정도가 필요합니다. 아래 대본을 자연스럽게 읽어 주세요. 지금 마이크가 없으면 건너뛰고 나중에 "목소리 등록" 메뉴에서 하면 됩니다.</p>
      {micOk === false && <div className="callout warn">마이크 권한이 없거나 장치가 없습니다. macOS는 시스템 설정 → 개인정보 보호 → 마이크에서 이 앱을 허용하세요. 지금은 건너뛰어도 됩니다.</div>}
      <div className="row">
        <div><label>목소리 이름</label><input type="text" value={name} disabled={!!voice} onChange={(e) => setName(e.target.value)} /></div>
        <div className="narrow"><label>등록된 샘플</label><div className="stat-inline">{n} / 3 <span className="muted">{n >= 3 ? "충분합니다" : n ? "하나 더 하면 좋아요" : ""}</span></div></div>
      </div>
      {script && (
        <>
          <div className="muted" style={{ marginBottom: 4 }}>대본 {idx + 1}/{scripts.length} · {script.title}</div>
          <div className="script-box">{script.text}</div>
        </>
      )}
      <div className="row" style={{ marginTop: 12, alignItems: "center" }}>
        <div className="narrow">
          {!recorder ? <button className="primary rec-btn" onClick={record} disabled={!!busy || !script}>● 녹음 시작</button>
            : <button className="danger rec-btn live" onClick={stop}>■ 녹음 끝내고 저장 ({elapsed.toFixed(1)}s)</button>}
        </div>
        <div>
          <div className="meter"><div style={{ width: `${Math.min(100, level * 400)}%` }} /></div>
          <div className="muted">{recorder ? (elapsed > 15 ? "15초가 넘었습니다. 끝내 주세요." : "녹음 중… 대본을 읽어 주세요 (8~15초)") : busy || "입력 레벨"}</div>
        </div>
        <div className="narrow"><button className="small" onClick={() => setIdx((i) => (i + 1) % Math.max(1, scripts.length))} disabled={!!recorder}>다른 대본</button></div>
      </div>
      {err && <div className="error">{err}</div>}
      <div className="wizard-actions">
        <button onClick={onBack}>← 이전</button>
        {n > 0 ? <button className="primary" onClick={onNext}>다음 →</button> : <button className="primary" onClick={onSkip}>지금은 건너뛰기 →</button>}
      </div>
    </>
  );
}
