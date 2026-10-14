import { useEffect, useRef, useState } from "react";
import { apiUrl, get, NoiseCatalogItem, NoiseSettings, postBlob } from "../lib/api";

interface Props {
  value: NoiseSettings;
  onChange: (v: NoiseSettings) => void;
  extra?: React.ReactNode;
}

export default function NoisePanel({ value, onChange, extra }: Props) {
  const [catalog, setCatalog] = useState<NoiseCatalogItem[]>([]);
  const [previewing, setPreviewing] = useState<string>("");
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [err, setErr] = useState("");

  const load = async () => {
    try {
      setCatalog(await get<NoiseCatalogItem[]>("/api/noises"));
    } catch {
      /* backend down */
    }
  };
  useEffect(() => {
    load();
  }, []);

  const toggle = (k: string) => {
    const types = value.types.includes(k) ? value.types.filter((x) => x !== k) : [...value.types, k];
    onChange({ ...value, types });
  };

  const play = (url: string, key: string) => {
    if (audioRef.current) {
      audioRef.current.pause();
    }
    const a = new Audio(url);
    audioRef.current = a;
    setPreviewing(key);
    a.onended = () => setPreviewing("");
    a.play().catch(() => setPreviewing(""));
  };

  const previewMix = async () => {
    setErr("");
    try {
      const { blob } = await postBlob("/api/noises/preview-mix", value);
      play(URL.createObjectURL(blob), "__mix");
    } catch (e) {
      setErr(String(e));
    }
  };

  const upload = async (file: File) => {
    setErr("");
    const fd = new FormData();
    fd.append("file", file);
    fd.append("label", file.name.replace(/\.[^.]+$/, ""));
    try {
      const r = await fetch(apiUrl("/api/noises"), { method: "POST", body: fd });
      if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
      const item = await r.json();
      await load();
      onChange({ ...value, types: [...value.types, item.id] });
    } catch (e) {
      setErr(String(e));
    }
  };

  const importFolder = async () => {
    const dir = await window.nursing?.chooseDirectory();
    if (!dir) return;
    setErr("");
    try {
      const r = await fetch(apiUrl("/api/noises/import-folder"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path: dir }) });
      if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
      const j = await r.json();
      await load();
      onChange({ ...value, types: [...value.types, ...j.added.map((a: { id: string }) => a.id)] });
      if (j.failed.length) setErr(`${j.failed.length}개 파일 실패: ${j.failed.map((f: { file: string }) => f.file).join(", ")}`);
    } catch (e) {
      setErr(String(e));
    }
  };

  const remove = async (k: string) => {
    if (!confirm("이 소음 파일을 삭제할까요?")) return;
    await fetch(apiUrl(`/api/noises/${k}`), { method: "DELETE" });
    onChange({ ...value, types: value.types.filter((x) => x !== k) });
    load();
  };

  return (
    <div className="panel">
      <h2>
        <label style={{ margin: 0, color: "inherit", fontSize: 14, display: "inline-flex", gap: 6, alignItems: "center" }}>
          <input type="checkbox" checked={value.enabled} onChange={(e) => onChange({ ...value, enabled: e.target.checked })} />
          주변 소음 포함 (현장감)
        </label>
        <span className="hint">녹음 중 선택한 소음이 랜덤한 시점·길이로 섞입니다</span>
      </h2>
      <div className="slider">
        <span className="muted" style={{ width: 70 }}>소음 크기</span>
        <input type="range" min={0} max={100} value={value.level} disabled={!value.enabled} onChange={(e) => onChange({ ...value, level: Number(e.target.value) })} />
        <span className="muted" style={{ width: 36 }}>{value.level}</span>
      </div>
      <div className="slider">
        <span className="muted" style={{ width: 70 }}>이벤트 빈도</span>
        <input type="range" min={1} max={15} step={0.5} value={value.density} disabled={!value.enabled} onChange={(e) => onChange({ ...value, density: Number(e.target.value) })} />
        <span className="muted" style={{ width: 36 }}>{value.density}/분</span>
      </div>
      <div className="checks" style={{ marginTop: 8 }}>
        <label>
          <input type="checkbox" checked={value.reverb} disabled={!value.enabled} onChange={(e) => onChange({ ...value, reverb: e.target.checked })} /> 병실 울림(리버브)
        </label>
        {extra}
      </div>
      <div className="pill-grid" style={{ marginTop: 10 }}>
        {catalog.map((n) => {
          const on = value.types.includes(n.key);
          return (
            <div key={n.key} className={"pill" + (on ? " on" : "")} onClick={() => value.enabled && toggle(n.key)} style={{ opacity: value.enabled ? 1 : 0.5 }}>
              <input type="checkbox" checked={on} disabled={!value.enabled} onChange={() => toggle(n.key)} onClick={(e) => e.stopPropagation()} />
              <div style={{ flex: 1 }}>
                <div className="t">{n.label}</div>
                <div className="d">{n.builtin ? (n.continuous ? "지속 배경음" : "랜덤 이벤트") : `내 파일 · ${n.duration ?? 0}s`}</div>
              </div>
              <button className="small" title="미리듣기" onClick={(e) => { e.stopPropagation(); play(apiUrl(`/api/noises/${n.key}/preview`), n.key); }}>
                {previewing === n.key ? "■" : "▶"}
              </button>
              {!n.builtin && (
                <button className="small danger" title="삭제" onClick={(e) => { e.stopPropagation(); remove(n.key); }}>×</button>
              )}
            </div>
          );
        })}
      </div>
      <div className="row" style={{ marginTop: 10 }}>
        <div className="narrow">
          <button onClick={previewMix} disabled={!value.enabled}>{previewing === "__mix" ? "■ 정지" : "▶ 소음 조합 미리듣기 (8초)"}</button>
        </div>
        <div className="narrow">
          <label className="small" style={{ display: "inline-block" }}>
            <span className="filebtn">＋ 소음 파일 추가 (wav/flac/ogg/mp3)</span>
            <input type="file" accept="audio/*,.wav,.flac,.ogg,.mp3,.m4a,.aac,.webm" style={{ display: "none" }} onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
          </label>
        </div>
        {window.nursing && (
          <div className="narrow"><button onClick={importFolder} title="MUSAN, DEMAND 같은 공개 소음 데이터셋 폴더나 직접 녹음한 병동 소음 폴더를 한 번에 가져옵니다">📁 폴더째 가져오기</button></div>
        )}
      </div>
      {err && <div className="error">{err}</div>}
    </div>
  );
}
