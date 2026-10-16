import { useEffect, useMemo, useState } from "react";
import JobProgress from "../components/JobProgress";
import { playVoiceDemo } from "../lib/voiceDemo";
import { apiUrl, get, ImportMapping, ImportTable, ImportTarget, Job, post, put, Settings, TemplateSchema, Voice } from "../lib/api";

const NONE = "";
const FIXED = "__fixed__";
const STYLES: [string, string][] = [["formal", "격식체"], ["mixed", "현장 혼합"], ["casual", "구어체"], ["chart", "기록체"]];
const KIND_LABEL: Record<string, string> = { text: "글", number: "숫자", select: "선택", multi: "복수 선택", bool: "예/아니오", datetime: "일시", date: "날짜", time: "시각" };

/** Guess a source column for a target from header words ("환자명" ↔ 환자 성명, "나이", "sex" ...). */
function guessColumn(target: ImportTarget, columns: string[]): string {
  const words = target.label.replace(/.*·\s*/, "").split(/[\s/()·]+/).filter((w) => w.length >= 2);
  const key = target.key.split(".").pop() || "";
  for (const c of columns) {
    const lc = c.toLowerCase();
    if (lc === key || words.some((w) => lc.includes(w.toLowerCase()) || w.toLowerCase().includes(lc))) return c;
  }
  return NONE;
}

export default function ImportPage() {
  const [table, setTable] = useState<ImportTable | null>(null);
  const [fileName, setFileName] = useState("");
  const [templates, setTemplates] = useState<TemplateSchema[]>([]);
  const [tkey, setTkey] = useState("s4");
  const [targets, setTargets] = useState<ImportTarget[]>([]);
  const [mapping, setMapping] = useState<ImportMapping>({ columns: {}, values: {}, fixed: {} });
  const [openValues, setOpenValues] = useState<Record<string, boolean>>({});
  const [rowIdx, setRowIdx] = useState(0);
  const [preview, setPreview] = useState("");
  const [warnings, setWarnings] = useState<string[]>([]);
  const [voices, setVoices] = useState<Voice[]>([]);
  const [voiceIds, setVoiceIds] = useState<string[]>([]);
  const [style, setStyle] = useState("formal");
  const [noiseOn, setNoiseOn] = useState(false);
  const [noiseLevel, setNoiseLevel] = useState(35);
  const [noiseProb, setNoiseProb] = useState(0.5);
  const [folder, setFolder] = useState("");
  const [limit, setLimit] = useState<number | "">("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  const [demoBusy, setDemoBusy] = useState("");
  const [demoError, setDemoError] = useState("");
  const [saved, setSaved] = useState("");

  useEffect(() => {
    get<TemplateSchema[]>("/api/templates").then(setTemplates).catch(() => undefined);
    get<Voice[]>("/api/voices").then((vs) => { setVoices(vs); setVoiceIds(vs.filter((v) => v.samples.length).map((v) => v.id)); }).catch(() => undefined);
    get<Settings>("/api/settings").then((s) => setStyle(s.default_style || "formal")).catch(() => undefined);
  }, []);
  useEffect(() => {
    (async () => {
      try {
        const tg = await get<ImportTarget[]>(`/api/import/targets/${tkey}`);
        setTargets(tg);
        const m = await get<ImportMapping>(`/api/import/mappings/${tkey}`);
        setMapping({ columns: m.columns || {}, values: m.values || {}, fixed: m.fixed || {} });
      } catch (e) { setErr(String(e)); }
    })();
  }, [tkey]);

  const upload = async (f: File) => {
    setErr(""); setBusy("파일 읽는 중…"); setPreview("");
    try {
      const fd = new FormData(); fd.append("file", f);
      const r = await fetch(apiUrl("/api/import/parse"), { method: "POST", body: fd });
      if (!r.ok) throw new Error((await r.json()).detail || `업로드 실패 (${r.status})`);
      const t = await r.json() as ImportTable;
      setTable(t); setFileName(f.name); setRowIdx(0);
    } catch (e) { setErr(String(e)); } finally { setBusy(""); }
  };

  const autoMap = () => {
    if (!table) return;
    const cols: Record<string, string> = { ...mapping.columns };
    for (const t of targets) if (!cols[t.key]) { const g = guessColumn(t, table.columns); if (g) cols[t.key] = g; }
    setMapping({ ...mapping, columns: cols });
  };
  const setCol = (key: string, col: string) => {
    const columns = { ...mapping.columns }; const fixed = { ...mapping.fixed };
    if (col === FIXED) { delete columns[key]; fixed[key] = fixed[key] ?? ""; }
    else if (col === NONE) { delete columns[key]; delete fixed[key]; }
    else { columns[key] = col; delete fixed[key]; }
    setMapping({ ...mapping, columns, fixed });
  };
  const setValueMap = (key: string, raw: string, v: string) => {
    const values = { ...mapping.values, [key]: { ...(mapping.values[key] || {}) } };
    if (v === "") delete values[key][raw]; else values[key][raw] = v;
    setMapping({ ...mapping, values });
  };
  const saveMapping = async () => {
    await put(`/api/import/mappings/${tkey}`, mapping);
    setSaved("저장됨"); setTimeout(() => setSaved(""), 1500);
  };

  const previewRow = async () => {
    if (!table) return;
    setBusy("미리보기 만드는 중…"); setErr("");
    try {
      const row = table.rows[Math.max(0, Math.min(rowIdx, table.rows.length - 1))];
      const b = await post<{ specs: { template: string; patient: unknown; form: unknown; datetime: string; style?: string }[]; warnings: string[] }>("/api/import/specs", { template: tkey, rows: [row], mapping });
      setWarnings(b.warnings);
      const sp = b.specs[0];
      const p = await post<{ spoken_text: string }>("/api/script/preview", { template: sp.template, patient: sp.patient, form: sp.form, datetime: sp.datetime, style: sp.style || style });
      setPreview(p.spoken_text);
    } catch (e) { setErr(String(e)); } finally { setBusy(""); }
  };

  const generate = async () => {
    if (!table) return;
    setErr("");
    try {
      const j = await post<Job & { warnings: string[]; warning_count: number }>("/api/import/generate", {
        template: tkey, rows: table.rows, mapping, limit: limit === "" ? null : limit, voice_ids: voiceIds, style,
        noise: { enabled: noiseOn, level: noiseLevel }, noise_prob: noiseProb, folder_name: folder,
      });
      setJobId(j.id);
      setWarnings(j.warnings);
    } catch (e) { setErr(String(e)); }
  };

  const mappedCount = useMemo(() => Object.keys(mapping.columns).length + Object.keys(mapping.fixed).length, [mapping]);
  const valueTargets = (t: ImportTarget) => ["select", "multi", "bool"].includes(t.kind) && mapping.columns[t.key];

  return (
    <div className="cols">
      <div>
        <div className="panel">
          <h2><span className="step-badge">1</span> 표 올리기 <span className="hint">CSV 또는 엑셀(xlsx) · 첫 줄이 열 이름 · 가명 데이터만</span></h2>
          <div className="row" style={{ alignItems: "center" }}>
            <label style={{ display: "inline-block" }}>
              <span className="primary" style={{ display: "inline-block", padding: "6px 12px", borderRadius: 8, cursor: "pointer", background: "var(--accent)", color: "#000" }}>📄 파일 선택</span>
              <input type="file" accept=".csv,.tsv,.txt,.xlsx,.xlsm" style={{ display: "none" }} onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
            </label>
            <div className="muted">{table ? `${fileName} · ${table.count}행 · 열 ${table.columns.length}개` : "아직 올린 표가 없습니다"}</div>
          </div>
          {table && (
            <div style={{ maxHeight: 180, overflow: "auto", marginTop: 8 }}>
              <table className="items">
                <thead><tr>{table.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
                <tbody>{table.rows.slice(0, 5).map((r, i) => <tr key={i}>{table.columns.map((c) => <td key={c} className="muted">{r[c]}</td>)}</tr>)}</tbody>
              </table>
            </div>
          )}
        </div>

        <div className="panel">
          <h2><span className="step-badge">2</span> 열 연결 <span className="hint">표의 열을 어느 항목에 넣을지, 셀 값이 어떤 선택지를 뜻하는지 정합니다</span>
            <span style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
              <button className="small" onClick={autoMap} disabled={!table}>🪄 이름으로 자동 연결</button>
              <button className="small" onClick={saveMapping}>💾 연결 저장</button>
              <span className="muted">{saved}</span>
            </span>
          </h2>
          <div className="row">
            <div>
              <label>기록 종류</label>
              <select value={tkey} onChange={(e) => setTkey(e.target.value)}>{templates.map((t) => <option key={t.key} value={t.key}>{t.title}</option>)}</select>
            </div>
            <div className="muted" style={{ alignSelf: "end" }}>연결된 항목 {mappedCount}개 · 연결하지 않은 항목은 기본값으로 읽습니다</div>
          </div>
          <div style={{ maxHeight: 520, overflow: "auto", marginTop: 8 }}>
            <table className="items">
              <thead><tr><th>항목</th><th>종류</th><th>표의 열</th><th>값의 뜻</th></tr></thead>
              <tbody>
                {targets.map((t) => {
                  const col = mapping.columns[t.key] ?? (t.key in mapping.fixed ? FIXED : NONE);
                  const distinct = col && col !== FIXED && table ? (table.distinct[col] || []) : [];
                  return (
                    <tr key={t.key}>
                      <td title={t.key}>{t.label}</td>
                      <td className="muted">{KIND_LABEL[t.kind] || t.kind}</td>
                      <td>
                        <select value={col} onChange={(e) => setCol(t.key, e.target.value)} style={{ minWidth: 120 }}>
                          <option value={NONE}>(사용 안 함)</option>
                          {table?.columns.map((c) => <option key={c} value={c}>{c}</option>)}
                          <option value={FIXED}>고정값…</option>
                        </select>
                        {col === FIXED && (
                          t.kind === "select" ? (
                            <select value={mapping.fixed[t.key] || ""} onChange={(e) => setMapping({ ...mapping, fixed: { ...mapping.fixed, [t.key]: e.target.value } })} style={{ marginTop: 4 }}>
                              <option value="">—</option>{t.options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                            </select>
                          ) : (
                            <input type="text" value={mapping.fixed[t.key] || ""} placeholder="모든 행에 같은 값" onChange={(e) => setMapping({ ...mapping, fixed: { ...mapping.fixed, [t.key]: e.target.value } })} style={{ marginTop: 4 }} />
                          )
                        )}
                      </td>
                      <td>
                        {valueTargets(t) ? (
                          <>
                            <button className="link" onClick={() => setOpenValues({ ...openValues, [t.key]: !openValues[t.key] })}>
                              {openValues[t.key] ? "▾" : "▸"} 값 {distinct.length}개 {Object.keys(mapping.values[t.key] || {}).length ? `(연결 ${Object.keys(mapping.values[t.key] || {}).length})` : ""}
                            </button>
                            {openValues[t.key] && (
                              <table className="items" style={{ marginTop: 4 }}>
                                <tbody>
                                  {distinct.map((raw) => (
                                    <tr key={raw}>
                                      <td className="muted" style={{ maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis" }} title={raw}>{raw}</td>
                                      <td>
                                        <select value={mapping.values[t.key]?.[raw] ?? ""} onChange={(e) => setValueMap(t.key, raw, e.target.value)}>
                                          <option value="">(그대로 / 자동)</option>
                                          {t.kind === "bool"
                                            ? <><option value="예">예 (체크)</option><option value="아니오">아니오</option></>
                                            : t.options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                                        </select>
                                      </td>
                                    </tr>
                                  ))}
                                  {!distinct.length && <tr><td className="muted">값이 없습니다</td></tr>}
                                </tbody>
                              </table>
                            )}
                          </>
                        ) : <span className="muted">{t.kind === "datetime" ? "2026-10-18 09:00 형식" : t.kind === "number" ? "숫자만 읽음" : "그대로"}</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div>
        <div className="panel">
          <h2><span className="step-badge">3</span> 미리보기 <span className="hint">한 행을 골라 대본이 어떻게 나오는지 봅니다</span></h2>
          <div className="row" style={{ alignItems: "end" }}>
            <div className="narrow"><label>행 번호</label><input type="number" min={1} max={table?.count || 1} value={rowIdx + 1} onChange={(e) => setRowIdx(Math.max(0, Number(e.target.value) - 1))} style={{ width: 80 }} /></div>
            <div className="narrow"><button onClick={previewRow} disabled={!table || !!busy}>📝 이 행으로 대본 보기</button></div>
            <div className="muted">{busy}</div>
          </div>
          {preview && <div className="preview" style={{ marginTop: 8, whiteSpace: "pre-wrap" }}>{preview}</div>}
          {warnings.length > 0 && <ul className="muted" style={{ marginTop: 6, paddingLeft: 18 }}>{warnings.slice(0, 20).map((w, i) => <li key={i}>{w}</li>)}</ul>}
          {err && <div className="error">{err}</div>}
        </div>

        <div className="panel">
          <h2><span className="step-badge">4</span> 행마다 녹음 만들기 <span className="hint">표의 행 하나가 녹음 하나</span></h2>
          <div className="field">
            <label>목소리 (여러 개 선택 시 무작위 배정)</label>
            <div className="checks">
              {voices.filter((v) => v.samples.length).map((v) => (
                <label key={v.id}><input type="checkbox" checked={voiceIds.includes(v.id)} onChange={() => setVoiceIds(voiceIds.includes(v.id) ? voiceIds.filter((x) => x !== v.id) : [...voiceIds, v.id])} /> {v.name}
                  <button type="button" className="link" style={{ marginLeft: 4 }} disabled={demoBusy === v.id} onClick={(e) => { e.preventDefault(); playVoiceDemo(v.id, setDemoBusy, setDemoError); }}>{demoBusy === v.id ? "⏳" : "🔊"}</button>
                </label>
              ))}
              {demoError && <span className="muted">{demoError}</span>}
            </div>
          </div>
          <div className="row">
            <div className="narrow"><label>말투</label><select value={style} onChange={(e) => setStyle(e.target.value)}>{STYLES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></div>
            <div className="narrow"><label>소음</label><label style={{ display: "inline-flex", gap: 6, alignItems: "center" }}><input type="checkbox" checked={noiseOn} onChange={(e) => setNoiseOn(e.target.checked)} /> 섞기</label></div>
            {noiseOn && <>
              <div className="narrow"><label>소음 크기</label><input type="number" min={0} max={100} value={noiseLevel} onChange={(e) => setNoiseLevel(Number(e.target.value))} style={{ width: 70 }} /></div>
              <div className="narrow"><label>소음 비율</label><input type="number" min={0} max={1} step={0.1} value={noiseProb} onChange={(e) => setNoiseProb(Number(e.target.value))} style={{ width: 70 }} /></div>
            </>}
            <div className="narrow"><label>앞에서 몇 행만</label><input type="number" min={1} max={table?.count || 1} value={limit} placeholder="전부" onChange={(e) => setLimit(e.target.value === "" ? "" : Number(e.target.value))} style={{ width: 80 }} /></div>
            <div><label>저장 폴더 이름</label><input type="text" value={folder} placeholder="import_날짜" onChange={(e) => setFolder(e.target.value)} /></div>
          </div>
          <div className="row" style={{ marginTop: 8 }}>
            <div className="narrow"><button className="primary" onClick={generate} disabled={!table || !mappedCount}>🚀 {limit === "" ? table?.count ?? 0 : Math.min(Number(limit), table?.count ?? 0)}개 생성 시작</button></div>
            <div className="muted">결과는 결과물·검수 화면에 나옵니다. 환자 정보는 반드시 가명이어야 합니다.</div>
          </div>
          {jobId && <div style={{ marginTop: 10 }}><JobProgress jobId={jobId} /></div>}
        </div>
      </div>
    </div>
  );
}
