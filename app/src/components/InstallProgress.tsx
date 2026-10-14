import { useEffect, useRef, useState } from "react";
import { SetupPhase, SetupProgress } from "../lib/api";
import { fmtSec } from "../lib/onboarding";

/**
 * Backend installer with a real progress model: phase list, percent, elapsed and an estimate.
 * Used by the first-run wizard and by the settings page.
 */
interface Props {
  withQwen: boolean;
  autoStart?: boolean;
  onDone?: (ok: boolean) => void;
  compact?: boolean;
}

const PHASES: { key: SetupPhase; label: string; est: string }[] = [
  { key: "venv", label: "Python 가상환경 만들기", est: "약 10초" },
  { key: "pip", label: "설치 도구(pip) 업데이트", est: "약 15초" },
  { key: "deps", label: "백엔드 패키지 설치", est: "1~3분" },
  { key: "qwen", label: "Qwen3-TTS + PyTorch 설치", est: "3~6분, 약 2 GB" },
  { key: "model", label: "한국어 복제 모델 내려받기 (1.7B)", est: "5~15분, 약 4.5 GB" },
  { key: "start", label: "백엔드 시작", est: "약 10초" },
];

export default function InstallProgress({ withQwen, autoStart, onDone, compact }: Props) {
  const [p, setP] = useState<SetupProgress | null>(null);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [log, setLog] = useState("");
  const [showLog, setShowLog] = useState(false);
  const [tick, setTick] = useState(0);
  const startedAt = useRef<number>(0);
  const started = useRef(false);

  useEffect(() => {
    if (!window.nursing) return;
    const off = window.nursing.onSetupProgress((prog) => setP(prog));
    window.nursing.onBackendLog((line) => setLog((l) => (l + line).slice(-30000)));
    return off;
  }, []);
  useEffect(() => {
    if (!running) return;
    const id = window.setInterval(() => setTick((t) => t + 1), 1000);
    return () => window.clearInterval(id);
  }, [running]);

  const start = async () => {
    if (!window.nursing || running) return;
    setRunning(true); setResult(null); setP(null); setLog("");
    startedAt.current = Date.now();
    try {
      const r = await window.nursing.setupBackend(withQwen);
      setResult(r);
      onDone?.(r.ok);
    } catch (e) {
      setResult({ ok: false, message: String(e) });
      onDone?.(false);
    } finally {
      setRunning(false);
    }
  };
  useEffect(() => {
    if (autoStart && !started.current) { started.current = true; start(); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoStart]);

  const cancel = async () => { await window.nursing?.cancelSetup(); };

  const phases = PHASES.filter((x) => withQwen || (x.key !== "qwen" && x.key !== "model"));
  const curIdx = p ? phases.findIndex((x) => x.key === p.phase) : -1;
  const elapsed = running ? Math.round((Date.now() - startedAt.current) / 1000) : p?.elapsed ?? 0;
  void tick;
  const failed = p?.phase === "error" || (result && !result.ok);
  const done = p?.phase === "done" || (result && result.ok);
  const totalEst = withQwen ? "보통 10~25분, 약 6.5 GB (인터넷 속도에 따라 다름)" : "보통 2~4분 (인터넷 속도에 따라 다름)";

  if (!window.nursing) {
    return <div className="callout">브라우저(개발) 모드에서는 앱 내 설치를 쓸 수 없습니다. 터미널에서 <span className="kbd">scripts/setup-backend.sh</span>를 실행하세요.</div>;
  }

  return (
    <div className={"installer" + (compact ? " compact" : "")}>
      {!running && !done && !failed && (
        <div className="row" style={{ alignItems: "center" }}>
          <div className="narrow"><button className="primary" onClick={start}>⬇ 설치 시작</button></div>
          <div className="muted">예상 소요 시간: <b>{totalEst}</b>. 이 PC에만 설치되며 인터넷 연결이 필요합니다.</div>
        </div>
      )}

      {(running || done || failed) && (
        <>
          <div className="install-head">
            <div className="install-pct">{done ? 100 : p?.pct ?? 0}<span>%</span></div>
            <div style={{ flex: 1 }}>
              <div className="install-msg">{done ? "설치가 끝났습니다 🎉" : failed ? "설치를 끝내지 못했습니다" : p?.message || "준비 중…"}</div>
              <div className="muted install-detail" title={p?.detail}>{failed ? result?.message || p?.message : p?.detail || " "}</div>
            </div>
            <div className="install-time">
              <div><span className="k">경과</span> {fmtSec(elapsed)}</div>
              {!done && !failed && <div><span className="k">남은 시간(예상)</span> {p?.eta !== null && p?.eta !== undefined ? `약 ${fmtSec(p.eta)}` : "계산 중"}</div>}
            </div>
          </div>
          <div className={"progress big" + (failed ? " bad" : "")}><div style={{ width: `${done ? 100 : p?.pct ?? 0}%` }} /></div>
          <ol className="phases">
            {phases.map((ph, i) => {
              const state = done ? "done" : failed ? (i < curIdx ? "done" : i === curIdx ? "fail" : "todo") : i < curIdx ? "done" : i === curIdx ? "cur" : "todo";
              return (
                <li key={ph.key} className={state}>
                  <span className="ico">{state === "done" ? "✓" : state === "cur" ? "●" : state === "fail" ? "✕" : i + 1}</span>
                  <span className="lbl">{ph.label}</span>
                  <span className="est">{ph.est}</span>
                </li>
              );
            })}
          </ol>
          <div className="row" style={{ marginTop: 6, alignItems: "center" }}>
            {running && <div className="narrow"><button className="danger small" onClick={cancel}>설치 취소</button></div>}
            {failed && <div className="narrow"><button className="primary small" onClick={start}>다시 시도</button></div>}
            <div className="narrow"><button className="small" onClick={() => setShowLog((v) => !v)}>{showLog ? "자세한 로그 닫기" : "자세한 로그 보기"}</button></div>
            {running && <div className="muted">창을 닫지 마세요. 로그에 "Collecting …"이 길게 반복되면 pip이 버전을 고르는 중입니다.</div>}
          </div>
          {showLog && <div className="log" style={{ marginTop: 8 }}>{log || "(로그 없음)"}</div>}
        </>
      )}
    </div>
  );
}
