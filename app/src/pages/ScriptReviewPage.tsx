import { useEffect, useMemo, useState } from "react";
import { Tab } from "../components/Sidebar";
import { del, get, patch, Patient, post, Settings, TemplateSchema } from "../lib/api";
import { setHandoff, takeHandoff } from "../lib/scriptStore";

interface PreviewResp { spoken_text: string; tts_text: string; seed: number; llm_polished: boolean; sentences?: string[] }
interface Item {
  id: string; template: string; record_kind: string; patient: Patient; form: Record<string, unknown>; datetime: string;
  style: string; seed: number; spoken_text: string; tts_text: string; llm_polished: boolean;
}
interface Flag { id: string; created: number; template: string; record_kind: string; patient: string; style: string; seed: number | null; sentence: string; note: string }

const STYLES: [string, string][] = [["formal", "격식체"], ["mixed", "현장 혼합"], ["casual", "구어체"], ["chart", "기록체"]];

/** Split a script into readable sentences (signal line first, then sentence by sentence). */
function sentencesOf(text: string): string[] {
  const out: string[] = [];
  for (const line of text.split("\n")) {
    const t = line.trim();
    if (!t) continue;
    for (const s of t.split(/(?<=[.!?])\s+/)) if (s.trim()) out.push(s.trim());
  }
  return out;
}

export default function ScriptReviewPage({ onTab }: { onTab?: (t: Tab) => void }) {
  const [templates, setTemplates] = useState<TemplateSchema[]>([]);
  const [chosen, setChosen] = useState<string[]>([]);
  const [style, setStyle] = useState("formal");
  const [count, setCount] = useState(20);
  const [items, setItems] = useState<Item[]>([]);
  const [sel, setSel] = useState("");
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  const [showTts, setShowTts] = useState(false);
  const [flags, setFlags] = useState<Flag[]>([]);
  const [markdown, setMarkdown] = useState("");
  const [settings, setSettings] = useState<Settings | null>(null);
  const [noteDraft, setNoteDraft] = useState<Record<string, string>>({});

  const loadFlags = async () => {
    const r = await get<{ items: Flag[]; markdown: string }>("/api/script-review");
    setFlags(r.items);
    setMarkdown(r.markdown);
  };
  useEffect(() => {
    (async () => {
      try {
        const ts = await get<TemplateSchema[]>("/api/templates");
        setTemplates(ts);
        setChosen(ts.map((t) => t.key));
        const s = await get<Settings>("/api/settings");
        setSettings(s);
        setStyle(s.default_style || "formal");
        await loadFlags();
        const h = takeHandoff();   // "대본 검토에서 열기" from the record page
        if (h) {
          const p = await post<PreviewResp>("/api/script/preview", { template: h.template, form: h.form, patient: h.patient, datetime: h.datetime, style: h.style, seed: h.seed });
          const it: Item = { id: `h${Date.now()}`, template: h.template, record_kind: ts.find((t) => t.key === h.template)?.signal_kind || h.template,
            patient: h.patient, form: h.form, datetime: h.datetime, style: h.style, seed: p.seed,
            spoken_text: h.text_override ?? p.spoken_text, tts_text: p.tts_text, llm_polished: p.llm_polished };
          setItems([it]);
          setSel(it.id);
        }
      } catch (e) {
        setErr(String(e));
      }
    })();
  }, []);

  const current = items.find((i) => i.id === sel);
  const kindOf = (key: string) => templates.find((t) => t.key === key)?.signal_kind || key;

  const makeMany = async () => {
    if (!chosen.length) return;
    setErr("");
    const made: Item[] = [];
    const n = Math.max(1, Math.min(100, count));
    for (let i = 0; i < n; i++) {
      setBusy(`대본 만드는 중… ${i + 1}/${n}`);
      const template = chosen[i % chosen.length];
      const seed = Math.floor(Math.random() * 1e9);
      try {
        const r = await post<{ patient: Patient; form: Record<string, unknown>; datetime: string }>("/api/random-patient", { template, seed });
        const p = await post<PreviewResp>("/api/script/preview", { template, form: r.form, patient: r.patient, datetime: r.datetime, style, seed });
        made.push({ id: `${seed}-${i}`, template, record_kind: kindOf(template), patient: r.patient, form: r.form, datetime: r.datetime,
          style, seed: p.seed, spoken_text: p.spoken_text, tts_text: p.tts_text, llm_polished: p.llm_polished });
        setItems([...made]);
        if (i === 0) setSel(made[0].id);
      } catch (e) {
        setErr(String(e));
        break;
      }
    }
    setBusy("");
  };

  const repreview = async (it: Item, opts: { style?: string; newSeed?: boolean; llm?: boolean }) => {
    setBusy("다시 만드는 중…");
    try {
      const st = opts.style ?? it.style;
      const p = await post<PreviewResp>("/api/script/preview", { template: it.template, form: it.form, patient: it.patient, datetime: it.datetime,
        style: st, seed: opts.newSeed ? null : it.seed, llm_polish: opts.llm ?? false });
      setItems((arr) => arr.map((x) => x.id === it.id ? { ...x, style: st, seed: p.seed, spoken_text: p.spoken_text, tts_text: p.tts_text, llm_polished: p.llm_polished } : x));
      setErr("");
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy("");
    }
  };

  const flagOf = (it: Item, sentence: string) => flags.find((f) => f.seed === it.seed && f.template === it.template && f.sentence === sentence);
  const toggleFlag = async (it: Item, sentence: string) => {
    const f = flagOf(it, sentence);
    if (f) await del(`/api/script-review/${f.id}`);
    else await post("/api/script-review", { template: it.template, record_kind: it.record_kind, patient: it.patient.name, style: it.style, seed: it.seed, sentence, note: "" });
    await loadFlags();
  };
  const saveNote = async (f: Flag, note: string) => {
    if (note === f.note) return;
    await patch(`/api/script-review/${f.id}`, { note });
    await loadFlags();
  };
  const copyMarkdown = async () => {
    try { await navigator.clipboard.writeText(markdown); setBusy("복사했습니다"); setTimeout(() => setBusy(""), 1500); } catch (e) { setErr(String(e)); }
  };
  const toRecord = (it: Item) => {
    setHandoff({ template: it.template, form: it.form, patient: it.patient, datetime: it.datetime, style: it.style, seed: it.seed });
    onTab?.("record");
  };

  const sentences = useMemo(() => current ? sentencesOf(current.spoken_text) : [], [current]);
  const flagCount = (it: Item) => flags.filter((f) => f.seed === it.seed && f.template === it.template).length;

  return (
    <div className="cols">
      <div>
        <div className="panel">
          <h2><span className="step-badge">1</span> 대본 만들기 <span className="hint">기록 종류와 말투를 고르고 무작위 대본을 여러 개 만듭니다</span></h2>
          <div className="checks">
            {templates.map((t) => (
              <label key={t.key}><input type="checkbox" checked={chosen.includes(t.key)} onChange={() => setChosen(chosen.includes(t.key) ? chosen.filter((k) => k !== t.key) : [...chosen, t.key])} /> {t.title}</label>
            ))}
          </div>
          <div className="row" style={{ marginTop: 8 }}>
            <div className="narrow">
              <label>말투</label>
              <select value={style} onChange={(e) => setStyle(e.target.value)}>{STYLES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
            </div>
            <div className="narrow">
              <label>개수</label>
              <input type="number" min={1} max={100} value={count} onChange={(e) => setCount(Number(e.target.value))} style={{ width: 70 }} />
            </div>
            <div className="narrow" style={{ alignSelf: "end" }}><button className="primary" onClick={makeMany} disabled={!!busy || !chosen.length}>🎲 대본 {count}개 만들기</button></div>
            <div className="muted" style={{ alignSelf: "end" }}>{busy}</div>
          </div>
          {err && <div className="error">{err}</div>}
        </div>
        <div className="panel">
          <h2><span className="step-badge">2</span> 목록 <span className="hint">클릭해서 읽기 · 표시한 문장 수</span></h2>
          <div style={{ maxHeight: 420, overflow: "auto" }}>
            <table className="items">
              <thead><tr><th>#</th><th>기록 종류</th><th>환자</th><th>말투</th><th>표시</th></tr></thead>
              <tbody>
                {items.map((it, i) => (
                  <tr key={it.id} onClick={() => setSel(it.id)} style={{ cursor: "pointer", background: sel === it.id ? "rgba(56,189,248,0.12)" : undefined }}>
                    <td>{i + 1}</td><td>{it.record_kind}</td><td>{it.patient.name}</td><td className="muted">{STYLES.find(([k]) => k === it.style)?.[1] || it.style}</td>
                    <td>{flagCount(it) ? <span className="badge warn">{flagCount(it)}</span> : ""}</td>
                  </tr>
                ))}
                {!items.length && <tr><td colSpan={5} className="muted">위에서 대본을 만들면 여기에 나옵니다.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
        <div className="panel">
          <h2><span className="step-badge">4</span> 표시한 문장 <span className="hint">{flags.length}개 · 이 목록을 복사해 전달하면 말투·문구 풀을 고칩니다</span>
            <span style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
              <button className="small" onClick={copyMarkdown} disabled={!flags.length}>📋 복사</button>
              <button className="small danger" onClick={async () => { if (confirm("표시한 문장을 모두 지울까요?")) { await del("/api/script-review"); await loadFlags(); } }} disabled={!flags.length}>지우기</button>
            </span>
          </h2>
          <ul className="list" style={{ maxHeight: 260, overflow: "auto" }}>
            {flags.map((f) => (
              <li key={f.id}>
                <div className="grow">
                  <div><span className="muted">[{f.record_kind || f.template}]</span> {f.sentence}</div>
                  <input type="text" placeholder="메모 (어떻게 말하는지)" defaultValue={f.note} style={{ fontSize: 12, marginTop: 2 }} onBlur={(e) => saveNote(f, e.target.value)} />
                </div>
                <button className="small danger" onClick={async () => { await del(`/api/script-review/${f.id}`); await loadFlags(); }}>삭제</button>
              </li>
            ))}
            {!flags.length && <li className="muted">아직 표시한 문장이 없습니다.</li>}
          </ul>
        </div>
      </div>

      <div>
        <div className="panel">
          <h2><span className="step-badge">3</span> 읽기 <span className="hint">병동에서 이렇게 말하지 않는 문장은 체크하세요</span></h2>
          {current ? (
            <>
              <div className="row" style={{ alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                <span className="badge">{current.record_kind}</span>
                <span className="muted">{current.patient.name} · {current.patient.diagnosis || ""} {current.patient.surgery || current.patient.regimen || ""}</span>
                <select value={current.style} onChange={(e) => repreview(current, { style: e.target.value })} title="이 대본만 다른 말투로">
                  {STYLES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                </select>
                <button className="small" onClick={() => repreview(current, { newSeed: true })}>🔀 다른 문구로</button>
                <button className="small" disabled={!settings || settings.llm_provider === "none"} title={settings?.llm_provider === "none" ? "설정에서 LLM API 키를 등록하세요" : ""} onClick={() => repreview(current, { llm: true })}>✨ LLM으로 다듬기</button>
                <button className="small" onClick={() => setShowTts((v) => !v)}>{showTts ? "정답 텍스트" : "TTS 발음 텍스트"}</button>
                <button className="small primary" onClick={() => toRecord(current)} title="이 대본 그대로 녹음 만들기 단계로">🎙 이 대본으로 녹음 만들기</button>
              </div>
              {current.llm_polished && <div className="muted">LLM 다듬기 적용됨</div>}
              {showTts ? (
                <div className="preview" style={{ marginTop: 8 }}>{current.tts_text}</div>
              ) : (
                <ul className="list" style={{ marginTop: 8 }}>
                  {sentences.map((s, i) => {
                    const f = flagOf(current, s);
                    return (
                      <li key={i} style={{ background: f ? "rgba(248,113,113,0.12)" : undefined }}>
                        <input type="checkbox" checked={!!f} onChange={() => toggleFlag(current, s)} title="이렇게 말 안 한다" />
                        <div className="grow" style={{ lineHeight: 1.6 }}>
                          {i === 0 ? <span className="signal">{s}</span> : s}
                          {f && (
                            <input type="text" placeholder="메모: 병동에서는 어떻게 말하나요?" value={noteDraft[f.id] ?? f.note} style={{ fontSize: 12, marginTop: 2 }}
                              onChange={(e) => setNoteDraft({ ...noteDraft, [f.id]: e.target.value })}
                              onBlur={(e) => saveNote(f, e.target.value)} onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()} />
                          )}
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </>
          ) : (
            <div className="empty"><b>왼쪽에서 대본을 만들고 하나를 고르세요</b>문장마다 체크해서 "이렇게 말 안 한다"를 표시할 수 있습니다.</div>
          )}
        </div>
      </div>
    </div>
  );
}
