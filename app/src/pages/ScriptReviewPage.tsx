import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Tab } from "../components/Sidebar";
import Term from "../components/Term";
import PatientPanel from "../components/PatientPanel";
import FormSections from "../components/FormSections";
import SignalSelect from "../components/SignalSelect";
import { del, DEFAULT_PATIENT, get, nowLocalIso, patch, Patient, post, Settings, TemplateSchema } from "../lib/api";
import { addToBasket, BasketItem, clearBasket, getBasket, removeFromBasket } from "../lib/scriptStore";

interface Turn { speaker: string; text: string }
interface PreviewResp { spoken_text: string; tts_text: string; seed: number; llm_polished: boolean; sentences?: string[]; issues?: string[]; turns?: Turn[] }
interface Item {
  id: string; template: string; record_kind: string; patient: Patient; form: Record<string, unknown>; datetime: string;
  style: string; seed: number; spoken_text: string; tts_text: string; llm_polished: boolean; issues: string[];
  text_override?: string | null; signal_format?: string; signal_aliases?: boolean | null; dialogue?: boolean; turns?: Turn[];
}
interface Flag { id: string; created: number; template: string; record_kind: string; patient: string; style: string; seed: number | null; sentence: string; note: string }

const STYLES: [string, string][] = [["formal", "격식체"], ["mixed", "현장 혼합"], ["casual", "구어체"], ["chart", "기록체"]];
const CUSTOM = "custom";

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

const LABEL: Record<string, string> = { nurse: "간호사", patient: "환자" };
/** Dialogue scripts are shown and edited with "간호사: / 환자: " prefixes; the backend strips them again. */
const labelled = (it: Item) => it.turns?.length ? it.turns.map((t) => `${LABEL[t.speaker] || t.speaker}: ${t.text}`).join("\n") : it.spoken_text;
const shown = (it: Item) => it.text_override ?? labelled(it);
/** Lines of the current text with their speaker (from the prefix, or nurse). */
function linesOf(text: string): { speaker: string; text: string }[] {
  return text.split("\n").map((l) => l.trim()).filter(Boolean).map((l) => {
    const m = /^(간호사|환자):\s*/.exec(l);
    return { speaker: m ? (m[1] === "환자" ? "patient" : "nurse") : "nurse", text: m ? l.slice(m[0].length) : l };
  });
}

/** 2 · 대본 생성: make scripts (🎲 many at once, or one by hand from the form), read them sentence by sentence,
 *  change register / wording / text, flag sentences the ward never says, and put the good ones in the basket
 *  that 3 · 녹음 만들기 reads (2026-10-17 split: text here, audio there). */
export default function ScriptReviewPage({ onTab }: { onTab?: (t: Tab) => void }) {
  const [templates, setTemplates] = useState<TemplateSchema[]>([]);
  const [mode, setMode] = useState<"random" | "custom">("random");
  const [chosen, setChosen] = useState<string[]>([]);
  const [style, setStyle] = useState("formal");
  const [count, setCount] = useState(20);
  const [items, setItems] = useState<Item[]>([]);
  const [sel, setSel] = useState("");
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  const [showTts, setShowTts] = useState(false);
  const [editing, setEditing] = useState(false);
  const [flags, setFlags] = useState<Flag[]>([]);
  const [markdown, setMarkdown] = useState("");
  const [settings, setSettings] = useState<Settings | null>(null);
  const [noteDraft, setNoteDraft] = useState<Record<string, string>>({});
  const [basket, setBasket] = useState<BasketItem[]>(getBasket());
  // 직접 설정 (the form that used to live on the record page)
  const [tkey, setTkey] = useState("s1");
  const [form, setForm] = useState<Record<string, unknown>>({});
  const [patient, setPatient] = useState<Patient>(DEFAULT_PATIENT);
  const [when, setWhen] = useState(nowLocalIso());
  const [customStyle, setCustomStyle] = useState("formal");
  const [customSeed, setCustomSeed] = useState<number | null>(null);
  const [signalFormat, setSignalFormat] = useState("");
  const [signalAliases, setSignalAliases] = useState<boolean | null>(null);
  const [dialogue, setDialogue] = useState(false);   // 간호정보조사만: 환자 대답 포함
  const [nursingDx, setNursingDx] = useState(true);  // 간호정보조사 "간호진단은 …입니다" 문장 포함 (user 2026-10-17: 넣을지 말지 결정)
  const withDx = (tpl: string, f: Record<string, unknown>) => (nursingDx || tpl !== "s1") ? f : Object.fromEntries(Object.entries(f).filter(([k]) => k !== "nursing_problems"));
  const debounce = useRef<number | null>(null);
  const template = useMemo(() => templates.find((t) => t.key === tkey), [templates, tkey]);

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
        setCustomStyle(s.default_style || "formal");
        await loadFlags();
      } catch (e) {
        setErr(String(e));
      }
    })();
  }, []);
  useEffect(() => {
    if (!tkey) return;
    get<Record<string, unknown>>(`/api/templates/${tkey}/defaults`).then((d) => { setForm(d); setCustomSeed(null); }).catch(() => undefined);
  }, [tkey]);

  const current = items.find((i) => i.id === sel);
  const kindOf = (key: string) => templates.find((t) => t.key === key)?.signal_kind || key;

  // ---- 직접 설정: live preview of the hand-made script as the "custom" item ----
  const previewCustom = useCallback(async (opts?: { newSeed?: boolean }) => {
    if (!template) return;
    try {
      const p = await post<PreviewResp>("/api/script/preview", {
        template: tkey, form: withDx(tkey, form), patient, datetime: when, style: customStyle, seed: opts?.newSeed ? null : customSeed,
        signal_format: signalFormat || undefined, signal_aliases: signalAliases ?? undefined, dialogue: dialogue && tkey === "s1",
      });
      setCustomSeed(p.seed);
      const it: Item = { id: CUSTOM, template: tkey, record_kind: kindOf(tkey), patient, form: withDx(tkey, form), datetime: when, style: customStyle, seed: p.seed,
        spoken_text: p.spoken_text, tts_text: p.tts_text, llm_polished: p.llm_polished, issues: p.issues || [], text_override: null,
        signal_format: signalFormat || undefined, signal_aliases: signalAliases, dialogue: dialogue && tkey === "s1", turns: p.turns || [] };
      setItems((arr) => arr.some((x) => x.id === CUSTOM) ? arr.map((x) => x.id === CUSTOM ? it : x) : [it, ...arr]);
      setSel(CUSTOM);
      setErr("");
    } catch (e) {
      setErr(String(e));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [template, tkey, form, patient, when, customStyle, customSeed, signalFormat, signalAliases, templates, dialogue]);
  useEffect(() => {
    if (mode !== "custom" || !template) return;
    if (debounce.current) window.clearTimeout(debounce.current);
    debounce.current = window.setTimeout(() => previewCustom(), 250);
    return () => { if (debounce.current) window.clearTimeout(debounce.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, form, patient, when, customStyle, tkey, template, signalFormat, signalAliases, dialogue]);
  const randomizeCustom = async () => {
    const r = await post<{ patient: Patient; form: Record<string, unknown>; datetime: string }>("/api/random-patient", { template: tkey });
    setPatient(r.patient);
    setForm(r.form);
    setWhen(r.datetime);
    setCustomSeed(null);
  };

  // ---- 🎲 many at once ----
  const makeMany = async () => {
    if (!chosen.length) return;
    setErr("");
    const made: Item[] = [];
    const n = Math.max(1, Math.min(100, count));
    for (let i = 0; i < n; i++) {
      setBusy(`대본 만드는 중… ${i + 1}/${n}`);
      const tpl = chosen[i % chosen.length];
      const seed = Math.floor(Math.random() * 1e9);
      try {
        const r = await post<{ patient: Patient; form: Record<string, unknown>; datetime: string }>("/api/random-patient", { template: tpl, seed });
        const dlg = dialogue && tpl === "s1";
        r.form = withDx(tpl, r.form);
        const p = await post<PreviewResp>("/api/script/preview", { template: tpl, form: r.form, patient: r.patient, datetime: r.datetime, style, seed, dialogue: dlg });
        made.push({ id: `${seed}-${i}`, template: tpl, record_kind: kindOf(tpl), patient: r.patient, form: r.form, datetime: r.datetime,
          style, seed: p.seed, spoken_text: p.spoken_text, tts_text: p.tts_text, llm_polished: p.llm_polished, issues: p.issues || [], dialogue: dlg, turns: p.turns || [] });
        setItems((arr) => [...arr.filter((x) => x.id === CUSTOM), ...made]);
        if (i === 0) setSel(made[0].id);
      } catch (e) {
        setErr(String(e));
        break;
      }
    }
    setBusy("");
  };

  const repreview = async (it: Item, opts: { style?: string; newSeed?: boolean; llm?: boolean }) => {
    if (it.id === CUSTOM) {   // the hand-made script follows its own controls
      if (opts.style) setCustomStyle(opts.style);
      if (opts.newSeed) { await previewCustom({ newSeed: true }); return; }
      if (!opts.llm) return;
    }
    setBusy("다시 만드는 중…");
    try {
      const st = opts.style ?? it.style;
      const p = await post<PreviewResp>("/api/script/preview", { template: it.template, form: it.form, patient: it.patient, datetime: it.datetime,
        style: st, seed: opts.newSeed ? null : it.seed, llm_polish: opts.llm ?? false, signal_format: it.signal_format, signal_aliases: it.signal_aliases ?? undefined, dialogue: !!it.dialogue });
      setItems((arr) => arr.map((x) => x.id === it.id ? { ...x, style: st, seed: p.seed, spoken_text: p.spoken_text, tts_text: p.tts_text, llm_polished: p.llm_polished, issues: p.issues || [], text_override: null, turns: p.turns || [] } : x));
      setEditing(false);
      setErr("");
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy("");
    }
  };
  /** 같은 대본 다른 말투로 (user 2026-10-17): same form, patient and seed, next register, as a new list entry. */
  const sameScriptOtherStyle = async (it: Item) => {
    const order = STYLES.map(([k]) => k);
    const next = order[(order.indexOf(it.style) + 1) % order.length];
    setBusy(`${STYLES.find(([k]) => k === next)?.[1]}로 만드는 중…`);
    try {
      const p = await post<PreviewResp>("/api/script/preview", { template: it.template, form: it.form, patient: it.patient, datetime: it.datetime,
        style: next, seed: it.seed, signal_format: it.signal_format, signal_aliases: it.signal_aliases ?? undefined, dialogue: !!it.dialogue });
      const copy: Item = { ...it, id: `${it.id}-${next}-${Date.now().toString(36)}`, style: next, seed: p.seed, spoken_text: p.spoken_text, tts_text: p.tts_text,
        llm_polished: p.llm_polished, issues: p.issues || [], text_override: null, turns: p.turns || [] };
      setItems((arr) => { const i = arr.findIndex((x) => x.id === it.id); const n = [...arr]; n.splice(i + 1, 0, copy); return n; });
      setSel(copy.id);
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

  const toBasket = (it: Item, go = false) => {
    const next = addToBasket({ template: it.template, form: it.form, patient: it.patient, datetime: it.datetime, style: it.style, seed: it.seed,
      text_override: it.text_override ?? null, record_kind: it.record_kind, spoken_text: shown(it), issues: it.issues, dialogue: !!it.dialogue, turns: it.turns });
    setBasket(next);
    setBusy(`바구니에 담았습니다 (${next.length}개)`);
    setTimeout(() => setBusy(""), 1500);
    if (go) onTab?.("record");
  };

  const sentences = useMemo(() => {
    if (!current) return [] as { speaker: string; text: string }[];
    if (!current.dialogue) return sentencesOf(shown(current)).map((text) => ({ speaker: "", text }));
    return linesOf(shown(current)).flatMap((l) => sentencesOf(l.text).map((text) => ({ speaker: l.speaker, text })));
  }, [current]);
  const flagCount = (it: Item) => flags.filter((f) => f.seed === it.seed && f.template === it.template).length;
  const inBasket = (it: Item) => basket.some((b) => b.template === it.template && b.seed === it.seed && b.style === it.style && (b.text_override ?? "") === (it.text_override ?? ""));

  return (
    <div className="cols">
      <div>
        <div className="panel">
          <h2><span className="step-badge">1</span> 대본 만들기
            <span style={{ marginLeft: "auto", display: "flex", gap: 4 }}>
              <button className={"small" + (mode === "random" ? " primary" : "")} onClick={() => setMode("random")}>🎲 무작위 여러 개</button>
              <button className={"small" + (mode === "custom" ? " primary" : "")} onClick={() => setMode("custom")}>✎ 직접 설정</button>
            </span>
          </h2>
          {mode === "random" ? (
            <>
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
              <label className="small" style={{ display: "inline-flex", gap: 6, alignItems: "center" }} title="간호정보조사에서 묻는 항목이 간호사 질문(~까요?)과 환자 대답(~어요/네/아니오, 80세 이상은 ~어/응/아니)으로 나뉩니다. 녹음은 두 목소리로 만들어집니다">
                <input type="checkbox" checked={dialogue} onChange={(e) => setDialogue(e.target.checked)} /> 간호정보조사는 환자 대답 포함(대화형)
              </label>
              <label className="small" style={{ display: "inline-flex", gap: 6, alignItems: "center", marginLeft: 12 }} title="끄면 간호정보조사 끝의 '간호진단은 …입니다' 문장이 빠집니다 (바구니에 담는 사양에서도 빠짐)">
                <input type="checkbox" checked={nursingDx} onChange={(e) => setNursingDx(e.target.checked)} /> 간호진단 문장 포함
              </label>
            </>
          ) : (
            <>
              <div className="checks">
                {templates.map((t) => (
                  <label key={t.key}><input type="radio" name="tpl" checked={tkey === t.key} onChange={() => setTkey(t.key)} /> {t.title}</label>
                ))}
              </div>
              {template && <div className="muted" style={{ marginTop: 6 }}>{template.description} · 시그널 기록종류: <b>{template.signal_kind}</b></div>}
              <SignalSelect value={signalFormat} onChange={setSignalFormat} aliases={signalAliases} onAliases={setSignalAliases} />
              <div className="row" style={{ marginTop: 10 }}>
                <div>
                  <label>시그널 발화 시각 (파일명에 사용)</label>
                  <input type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} />
                </div>
                <div className="narrow"><button onClick={() => setWhen(nowLocalIso())}>지금</button></div>
                <div>
                  <label>말투</label>
                  <select value={customStyle} onChange={(e) => setCustomStyle(e.target.value)}>
                    <option value="formal">격식체 위주 (~하였습니다, 기본)</option>
                    <option value="mixed">현장 혼합</option>
                    <option value="casual">구어체 위주 (~하시구요)</option>
                    <option value="chart">기록체 (~함/~됨, 차팅하듯)</option>
                  </select>
                </div>
              </div>
              {tkey === "s1" && (
                <label className="small" style={{ display: "inline-flex", gap: 6, alignItems: "center" }} title="묻는 항목이 간호사 질문(~까요?)과 환자 대답(~어요/네/아니오, 80세 이상은 ~어/응/아니)으로 나뉩니다. 녹음은 두 목소리로 만들어집니다">
                  <input type="checkbox" checked={dialogue} onChange={(e) => setDialogue(e.target.checked)} /> 환자 대답 포함(대화형)
                </label>
              )}
              <div className="muted">{busy}</div>
            </>
          )}
          {err && <div className="error">{err}</div>}
        </div>
        {mode === "custom" && (
          <>
            <PatientPanel patient={patient} onChange={setPatient} onRandom={randomizeCustom} step={2} />
            <FormSections template={template} form={form} onChange={setForm} step={3} />
          </>
        )}
        <div className="panel">
          <h2><span className="step-badge">{mode === "custom" ? 5 : 2}</span> 목록 <span className="hint">클릭해서 읽기 · 표시한 문장 수 · 🧺 바구니에 담김</span></h2>
          <div style={{ maxHeight: 420, overflow: "auto" }}>
            <table className="items">
              <thead><tr><th>#</th><th>기록 종류</th><th>환자</th><th>말투</th><th>표시</th><th>🧺</th></tr></thead>
              <tbody>
                {items.map((it, i) => (
                  <tr key={it.id} onClick={() => { setSel(it.id); setEditing(false); }} style={{ cursor: "pointer", background: sel === it.id ? "rgba(56,189,248,0.12)" : undefined }}>
                    <td>{it.id === CUSTOM ? "✎" : i + (items.some((x) => x.id === CUSTOM) ? 0 : 1)}</td><td>{it.record_kind}{it.dialogue ? " 💬" : ""}</td><td>{it.patient.name}</td>
                    <td className="muted">{STYLES.find(([k]) => k === it.style)?.[1] || it.style}</td>
                    <td>{flagCount(it) ? <span className="badge warn">{flagCount(it)}</span> : ""}</td>
                    <td>{inBasket(it) ? "✓" : ""}</td>
                  </tr>
                ))}
                {!items.length && <tr><td colSpan={6} className="muted">위에서 대본을 만들면 여기에 나옵니다.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
        <div className="panel">
          <h2><span className="step-badge">{mode === "custom" ? 7 : 4}</span> 표시한 문장 <span className="hint">{flags.length}개 · 이 목록을 복사해 전달하면 말투·문구 풀을 고칩니다</span>
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
          <h2><span className="step-badge">{mode === "custom" ? 6 : 3}</span> 읽기 <span className="hint">병동에서 이렇게 말하지 않는 문장은 체크하세요 · 마음에 들면 바구니에</span></h2>
          {current ? (
            <>
              <div className="row" style={{ alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                <span className="badge">{current.record_kind}</span>
                <span className="muted">{current.patient.name} · {current.patient.diagnosis || ""} {current.patient.surgery || current.patient.regimen || ""}</span>
                <select value={current.style} onChange={(e) => repreview(current, { style: e.target.value })} title="이 대본만 다른 말투로 바꿉니다">
                  {STYLES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                </select>
                <button className="small" onClick={() => sameScriptOtherStyle(current)} title="같은 환자·같은 체크 상태·같은 시드로 다음 말투 버전을 하나 더 만듭니다">🗣 같은 대본 다른 말투로</button>
                <button className="small" onClick={() => repreview(current, { newSeed: true })}>🔀 다른 문구로</button>
                <button className="small" disabled={!settings || settings.llm_provider === "none"} title={settings?.llm_provider === "none" ? "설정에서 LLM API 키를 등록하세요" : ""} onClick={() => repreview(current, { llm: true })}>✨ LLM으로 다듬기</button>
                <button className="small" onClick={() => { setShowTts((v) => !v); setEditing(false); }}>{showTts ? "정답 텍스트" : <Term k="TTS 발음 텍스트" />}</button>
                <button className={"small" + (editing ? " primary" : "")} onClick={() => { setEditing((v) => !v); setShowTts(false); }} title="문장을 직접 고칩니다. 고친 텍스트가 그대로 녹음·정답이 됩니다">✎ 직접 고치기</button>
              </div>
              <div className="row" style={{ alignItems: "center", gap: 6, marginTop: 4 }}>
                <button className="small primary" onClick={() => toBasket(current)} title="녹음 만들기 단계의 바구니에 담습니다">🧺 바구니에 담기{inBasket(current) ? " ✓" : ""}</button>
                <button className="small" onClick={() => toBasket(current, true)} title="담고 바로 녹음 만들기로 이동">🎙 담고 녹음 만들기로 →</button>
                {current.llm_polished && <span className="muted">LLM 다듬기 적용됨</span>}
                {current.dialogue && <span className="badge" title="녹음 만들기에서 환자 목소리를 고를 수 있습니다">💬 대화형 · 환자 {current.patient.age ?? ""}세{(current.patient.age ?? 0) >= 80 ? " 반말" : ""}</span>}
                {current.text_override != null && <span className="badge warn">직접 수정됨</span>}
              </div>
              {current.issues.length > 0 && <div className="badge bad" style={{ marginTop: 6 }} title={current.issues.join("\n")}>⚠ 자동 검사 모순 {current.issues.length}개: {current.issues.join(" · ")}</div>}
              {showTts ? (
                <div className="preview" style={{ marginTop: 8 }}>{current.tts_text}</div>
              ) : editing ? (
                <textarea className="preview" rows={12} style={{ marginTop: 8 }} spellCheck={false} value={shown(current)}
                  onChange={(e) => setItems((arr) => arr.map((x) => x.id === current.id ? { ...x, text_override: e.target.value } : x))} />
              ) : (
                <ul className="list" style={{ marginTop: 8 }}>
                  {sentences.map(({ speaker, text: s }, i) => {
                    const f = flagOf(current, s);
                    return (
                      <li key={i} style={{ background: f ? "rgba(248,113,113,0.12)" : speaker === "patient" ? "rgba(167,139,250,0.08)" : undefined }}>
                        <input type="checkbox" checked={!!f} onChange={() => toggleFlag(current, s)} title="이렇게 말 안 한다" />
                        <div className="grow" style={{ lineHeight: 1.6 }}>
                          {speaker && <span className="badge" style={{ marginRight: 6 }}>{LABEL[speaker]}</span>}
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
            <div className="empty"><b>왼쪽에서 대본을 만들고 하나를 고르세요</b>🎲로 여러 개를 한 번에 만들거나, ✎ 직접 설정으로 환자와 상태를 골라 하나를 만듭니다. 문장마다 체크해서 "이렇게 말 안 한다"를 표시할 수 있습니다.</div>
          )}
        </div>

        <div className="panel">
          <h2>🧺 대본 바구니 <span className="hint">{basket.length}개 · 녹음 만들기 단계가 이 목록을 읽습니다</span>
            <span style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
              <button className="small primary" disabled={!basket.length} onClick={() => onTab?.("record")}>🎙 녹음 만들기로 →</button>
              <button className="small danger" disabled={!basket.length} onClick={() => { if (confirm("바구니를 비울까요?")) { clearBasket(); setBasket([]); } }}>비우기</button>
            </span>
          </h2>
          <ul className="list" style={{ maxHeight: 220, overflow: "auto" }}>
            {basket.map((b) => (
              <li key={b.id}>
                <div className="grow"><span className="badge">{b.record_kind}</span> {b.patient.name} · <span className="muted">{STYLES.find(([k]) => k === b.style)?.[1] || b.style} · {b.spoken_text.length}자{b.text_override != null ? " · 직접 수정" : ""}{b.issues.length ? ` · ⚠${b.issues.length}` : ""}</span></div>
                <button className="small danger" onClick={() => setBasket(removeFromBasket(b.id))}>빼기</button>
              </li>
            ))}
            {!basket.length && <li className="muted">읽어 본 대본을 "🧺 바구니에 담기"로 모으세요.</li>}
          </ul>
        </div>
      </div>
    </div>
  );
}
