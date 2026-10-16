import { useEffect, useState } from "react";
import { playVoiceDemo } from "../lib/voiceDemo";

/** "🔊 예시 문장 듣기" for a voice: a fixed sentence synthesised with the voice (bundled or cached on the server),
 *  with pitch/tempo sliders. ``initialPitch``/``initialTempo`` are the voice's saved preset; ``onSave`` stores the
 *  current sliders as the preset (applied to every recording made with the voice). The source recordings are never played here. */
export default function VoiceDemo({ voiceId, disabled, compact, initialPitch = 0, initialTempo = 1, onSave }:
  { voiceId: string; disabled?: boolean; compact?: boolean; initialPitch?: number; initialTempo?: number;
    onSave?: (pitch: number, tempo: number) => Promise<void> | void }) {
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [pitch, setPitch] = useState(initialPitch);
  const [tempo, setTempo] = useState(initialTempo);
  const [saving, setSaving] = useState(false);
  useEffect(() => { setPitch(initialPitch); setTempo(initialTempo); }, [voiceId, initialPitch, initialTempo]);
  const dirty = pitch !== initialPitch || tempo !== initialTempo;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
      <button type="button" onClick={() => playVoiceDemo(voiceId, setBusy, setError, { pitch, tempo })} disabled={disabled || !voiceId || busy === voiceId}
        title="이 목소리로 고정 예시 문장을 읽은 샘플을 들려줍니다 (원음은 재생하지 않음)">
        {busy === voiceId ? "⏳ 예시 만드는 중…" : compact ? "🔊 예시 듣기" : "🔊 예시 문장 듣기"}
      </button>
      <label className="muted" style={{ display: "inline-flex", alignItems: "center", gap: 4 }} title="음높이 (반음)">
        음높이 <input type="range" min={-6} max={6} step={1} value={pitch} onChange={(e) => setPitch(Number(e.target.value))} style={{ width: 90 }} />
        <span style={{ minWidth: 28 }}>{pitch > 0 ? `+${pitch}` : pitch}</span>
      </label>
      <label className="muted" style={{ display: "inline-flex", alignItems: "center", gap: 4 }} title="속도 (배)">
        속도 <input type="range" min={0.8} max={1.3} step={0.05} value={tempo} onChange={(e) => setTempo(Number(e.target.value))} style={{ width: 90 }} />
        <span style={{ minWidth: 34 }}>{tempo.toFixed(2)}×</span>
      </label>
      {(pitch !== 0 || tempo !== 1) && <button type="button" className="link" onClick={() => { setPitch(0); setTempo(1); }}>원래대로</button>}
      {onSave && (
        <button type="button" className="small" disabled={!dirty || saving} title="이 목소리로 녹음을 만들 때마다 이 음높이·속도가 적용됩니다"
          onClick={async () => { setSaving(true); try { await onSave(pitch, tempo); } finally { setSaving(false); } }}>
          {saving ? "저장 중…" : "프리셋 저장"}
        </button>
      )}
      {onSave && !dirty && (initialPitch !== 0 || initialTempo !== 1) && <span className="muted">프리셋 적용 중 (생성 시에도 적용)</span>}
      {error && <span className="muted">{error}</span>}
    </div>
  );
}
