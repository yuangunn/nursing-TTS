import { useEffect, useState } from "react";
import { BundleInfo } from "../lib/api";

/** 인트라넷(오프라인) 설치 (user 2026-10-17): pick the zip that scripts/build-offline-bundle made on an internet PC;
 *  it is unpacked into the app data folder and the backend runs on the bundled Python, no pip or model download. */
export default function OfflineBundle({ onDone, compact }: { onDone?: (ok: boolean) => void; compact?: boolean }) {
  const [info, setInfo] = useState<BundleInfo | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const load = () => window.nursing?.offlineBundleInfo().then(setInfo).catch(() => undefined);
  useEffect(() => { load(); }, []);
  if (!window.nursing) return null;
  const pick = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const r = await window.nursing!.importOfflineBundle();
      if (r.message !== "취소됨") setMsg({ ok: r.ok, text: r.message });
      await load();
      if (r.ok) onDone?.(true);
    } catch (e) {
      setMsg({ ok: false, text: String(e) });
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className={compact ? "" : "callout"} style={{ marginTop: compact ? 6 : 10 }}>
      <div className="row" style={{ alignItems: "center", marginBottom: 4 }}>
        <div className="narrow"><button onClick={pick} disabled={busy} title="인터넷이 없는 PC용. 다른 PC에서 scripts/build-offline-bundle.sh(.ps1)로 만든 zip을 고르면 Python과 패키지(선택: 모델)가 앱 데이터 폴더에 설치됩니다">
          {busy ? "번들 설치 중… (1~3분)" : "📦 오프라인 번들(zip) 가져오기…"}
        </button></div>
        {info?.present && <span className="badge ok" title={info.path}>{info.source === "installer" ? "설치본에 내장된 백엔드" : "오프라인 번들 사용 중"} · Python {info.python}{info.qwen ? " · Qwen3-TTS" : ""}{info.models ? " · 모델 포함" : ""}</span>}
        {!compact && <div className="muted">인터넷이 없는 PC라면 pip 대신 이 방법으로. 번들은 인터넷 되는 PC에서 <span className="kbd">scripts/build-offline-bundle.sh --qwen</span> (Windows: <span className="kbd">.ps1 -Qwen</span>)로 만듭니다. 모델 파일은 번들에 넣거나(<span className="kbd">--models</span>) 나중에 설정 → 로컬 모델 폴더에 복사하고, 이 PC의 목소리·소음까지 옮기려면 <span className="kbd">--data</span>를 붙입니다. 기본 목소리 15명과 병동 소음 클립은 모든 설치 파일에 들어 있어 첫 실행 때 자동으로 생깁니다. 릴리스의 "-offline" 설치 파일(dmg/exe)은 백엔드와 복제 엔진까지 이미 들어 있어 번들 없이도 바로 뜹니다(온디바이스 모델만 별도).</div>}
      </div>
      {msg && <div className={msg.ok ? "ok-text" : "error"}>{msg.text}</div>}
    </div>
  );
}
