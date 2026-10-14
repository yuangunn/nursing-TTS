import { useEffect, useState } from "react";
import { AugmentSettings, get } from "../lib/api";

interface Props {
  value: AugmentSettings;
  onChange: (v: AugmentSettings) => void;
  disfluency: number | "random";
  onDisfluency: (v: number | "random") => void;
  allowRandomDisfluency?: boolean;
}

const DIS_LABEL: Record<string, string> = { "0": "없음 (깔끔한 구술)", "1": "약간 (가끔 '음…')", "2": "보통 (추임새·반복)", "3": "많음 (숫자 정정까지)", random: "녹음마다 무작위" };

export default function AugmentPanel({ value, onChange, disfluency, onDisfluency, allowRandomDisfluency }: Props) {
  const [presets, setPresets] = useState<{ key: string; label: string }[]>([]);
  useEffect(() => {
    get<{ key: string; label: string }[]>("/api/augment/presets").then(setPresets).catch(() => undefined);
  }, []);
  const toggle = (k: string) => onChange({ ...value, channels: value.channels.includes(k) ? value.channels.filter((x) => x !== k) : [...value.channels, k] });
  return (
    <div className="panel">
      <h2>
        <label style={{ margin: 0, color: "inherit", fontSize: 14, display: "inline-flex", gap: 6, alignItems: "center" }}>
          <input type="checkbox" checked={value.enabled} onChange={(e) => onChange({ ...value, enabled: e.target.checked })} />
          녹음 장비·말속도 다양화 (증강)
        </label>
        <span className="hint">ASR 학습 데이터 관례: 같은 발화를 다른 마이크·속도로</span>
      </h2>
      <div className="pill-grid">
        {presets.map((p) => {
          const on = value.channels.includes(p.key);
          return (
            <div key={p.key} className={"pill" + (on ? " on" : "")} style={{ opacity: value.enabled ? 1 : 0.5 }} onClick={() => value.enabled && toggle(p.key)}>
              <input type="checkbox" checked={on} disabled={!value.enabled} onChange={() => toggle(p.key)} onClick={(e) => e.stopPropagation()} />
              <div className="t">{p.label}</div>
            </div>
          );
        })}
      </div>
      <div className="slider" style={{ marginTop: 10 }}>
        <span className="muted" style={{ width: 90 }}>말속도 범위</span>
        <input type="number" step={0.01} min={0.7} max={1} value={value.speed_min} disabled={!value.enabled} onChange={(e) => onChange({ ...value, speed_min: Number(e.target.value) })} style={{ width: 70 }} />
        <span className="muted">~</span>
        <input type="number" step={0.01} min={1} max={1.4} value={value.speed_max} disabled={!value.enabled} onChange={(e) => onChange({ ...value, speed_max: Number(e.target.value) })} style={{ width: 70 }} />
        <span className="muted" style={{ marginLeft: 10 }}>적용 확률</span>
        <input type="range" min={0} max={1} step={0.05} value={value.speed_prob} disabled={!value.enabled} onChange={(e) => onChange({ ...value, speed_prob: Number(e.target.value) })} />
        <span className="muted" style={{ width: 36 }}>{Math.round(value.speed_prob * 100)}%</span>
      </div>
      <div className="slider">
        <span className="muted" style={{ width: 90 }}>음량 편차 ±dB</span>
        <input type="range" min={0} max={12} step={1} value={value.gain_db_range} disabled={!value.enabled} onChange={(e) => onChange({ ...value, gain_db_range: Number(e.target.value) })} />
        <span className="muted" style={{ width: 36 }}>{value.gain_db_range}</span>
        <span className="muted" style={{ marginLeft: 10 }}>과입력 클리핑 확률</span>
        <input type="range" min={0} max={0.5} step={0.05} value={value.clip_prob} disabled={!value.enabled} onChange={(e) => onChange({ ...value, clip_prob: Number(e.target.value) })} />
        <span className="muted" style={{ width: 36 }}>{Math.round(value.clip_prob * 100)}%</span>
      </div>
      <div className="row" style={{ marginTop: 10, marginBottom: 0 }}>
        <div>
          <label>구어 흐트러짐 (추임새 "음…", 말 반복, "37.4, 아니 37.1" 숫자 정정)</label>
          <select value={String(disfluency)} onChange={(e) => onDisfluency(e.target.value === "random" ? "random" : Number(e.target.value))}>
            {allowRandomDisfluency && <option value="random">{DIS_LABEL.random}</option>}
            {["0", "1", "2", "3"].map((k) => (
              <option key={k} value={k}>{k} · {DIS_LABEL[k]}</option>
            ))}
          </select>
          <div className="example">추임새는 음성에만 들어가고 정답 텍스트는 깔끔하게 유지됩니다 (JSON에 추임새 포함 verbatim_text 별도 저장, 내보내기 시 선택).</div>
        </div>
      </div>
    </div>
  );
}
