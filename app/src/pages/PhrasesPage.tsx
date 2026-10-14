import { useEffect, useMemo, useState } from "react";
import { apiUrl, del, get, post, put } from "../lib/api";

interface Slot { slot: string; label: string; builtin: string[]; override: string[] | null }
interface PField { key: string; label: string; kind: string; unit?: string; placeholder?: string; example?: string; slots: Slot[] }
interface PSection { key: string; title: string; fields: PField[] }
interface PTemplate { key: string; title: string; sections: PSection[] }
interface Tree { templates: PTemplate[]; auto_style_expand: boolean; total_variants: number; effective_variants: number; overridden_slots: number }

const PLACEHOLDERS = "{v} 값 · {name} 환자명 · {age} {sex} · {dx} 진단 · {surgery} 수술명(무작위 표기) · {surgery_en} · {surgery_ko} · {surgery_abbr} · {prof} 교수 · {dept} 과 · {pod} · {op_date} · {drain_amount} 등 같은 템플릿의 숫자/텍스트 항목 키";

export default function PhrasesPage() {
  const [tree, setTree] = useState<Tree | null>(null);
  const [tkey, setTkey] = useState("s1");
  const [fkey, setFkey] = useState("");
  const [skey, setSkey] = useState("");
  const [draft, setDraft] = useState<string[]>([]);
  const [dirty, setDirty] = useState(false);
  const [samples, setSamples] = useState<string[]>([]);
  const [style, setStyle] = useState("mixed");
  const [msg, setMsg] = useState("");
  const [q, setQ] = useState("");

  const load = async () => setTree(await get<Tree>("/api/phrases"));
  useEffect(() => {
    load().catch((e) => setMsg(String(e)));
  }, []);

  const template = tree?.templates.find((t) => t.key === tkey);
  const field = useMemo(() => template?.sections.flatMap((s) => s.fields).find((f) => f.key === fkey), [template, fkey]);
  const slot = field?.slots.find((s) => s.slot === skey);

  const select = (f: PField, s: Slot) => {
    if (dirty && !confirm("저장하지 않은 수정이 있습니다. 버릴까요?")) return;
    setFkey(f.key);
    setSkey(s.slot);
    setDraft([...(s.override ?? s.builtin)]);
    setDirty(false);
    setSamples([]);
  };

  const save = async () => {
    if (!slot) return;
    await put("/api/phrases", { template: tkey, field: fkey, slot: skey, phrases: draft });
    await load();
    setDirty(false);
    setMsg("저장됨");
    setTimeout(() => setMsg(""), 1500);
  };
  const reset = async () => {
    if (!slot || !confirm("기본 문장으로 되돌릴까요?")) return;
    await del(`/api/phrases?template=${tkey}&field=${fkey}&slot=${skey}`);
    await load();
    const t = (await get<Tree>("/api/phrases")).templates.find((x) => x.key === tkey);
    const s = t?.sections.flatMap((x) => x.fields).find((f) => f.key === fkey)?.slots.find((x) => x.slot === skey);
    setDraft([...(s?.builtin ?? [])]);
    setDirty(false);
  };
  const sample = async () => {
    const r = await post<{ samples: string[] }>("/api/phrases/sample", { template: tkey, field: fkey, slot: skey, phrases: draft, style });
    setSamples(r.samples);
  };
  const exportAll = async () => {
    const data = await get("/api/phrases/export");
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "phrases.json";
    a.click();
  };
  const importAll = async (file: File) => {
    const data = JSON.parse(await file.text());
    const r = await post<{ slots: number }>("/api/phrases/import", { data });
    setMsg(`${r.slots}개 항목 가져옴`);
    await load();
  };
  const toggleExpand = async (v: boolean) => {
    await put("/api/settings", { auto_style_expand: v });
    await load();
  };

  const matches = (f: PField, s: Slot) => !q || `${f.label} ${s.label} ${f.key} ${s.slot} ${(s.override ?? s.builtin).join(" ")}`.includes(q);

  return (
    <div className="cols" style={{ gridTemplateColumns: "minmax(420px, 1fr) minmax(480px, 1.2fr)" }}>
      <div>
        <div className="panel">
          <h2>말투 라이브러리
            <span style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
              <button className="small" onClick={exportAll}>내보내기</button>
              <label className="filebtn" style={{ padding: "4px 9px", fontSize: 12 }}>가져오기<input type="file" accept=".json" style={{ display: "none" }} onChange={(e) => e.target.files?.[0] && importAll(e.target.files[0])} /></label>
            </span>
          </h2>
          {tree && (
            <div className="stat">
              <div><div className="k">기본 문장</div><div className="v">{tree.total_variants}</div></div>
              <div><div className="k">어미 확장 포함</div><div className="v">{tree.effective_variants}</div></div>
              <div><div className="k">수정한 항목</div><div className="v">{tree.overridden_slots}</div></div>
            </div>
          )}
          <div className="checks" style={{ marginBottom: 8 }}>
            <label title="'~하였습니다.'를 '~했고요,' '~했어요.'로 자동 파생해 변형 수를 3배로 늘립니다">
              <input type="checkbox" checked={!!tree?.auto_style_expand} onChange={(e) => toggleExpand(e.target.checked)} /> 어미 자동 확장 (격식 → ~고요, / ~어요.)
            </label>
          </div>
          <div className="row">
            <div>
              <select value={tkey} onChange={(e) => { setTkey(e.target.value); setFkey(""); setSkey(""); setDirty(false); }}>
                {tree?.templates.map((t) => <option key={t.key} value={t.key}>{t.title}</option>)}
              </select>
            </div>
            <div><input type="text" placeholder="항목/문장 검색" value={q} onChange={(e) => setQ(e.target.value)} /></div>
          </div>
          <div style={{ maxHeight: 560, overflow: "auto" }}>
            {template?.sections.map((sec) => (
              <div className="section" key={sec.key}>
                <div className="section-head"><strong>{sec.title}</strong></div>
                {sec.fields.map((f) => f.slots.filter((s) => matches(f, s)).map((s) => {
                  const n = (s.override ?? s.builtin).length;
                  const active = f.key === fkey && s.slot === skey;
                  return (
                    <div key={f.key + s.slot} className={"pill" + (active ? " on" : "")} style={{ marginBottom: 4 }} onClick={() => select(f, s)}>
                      <div style={{ flex: 1 }}>
                        <div className="t">{f.label} <span className="muted">› {s.label}</span></div>
                        <div className="d">{n}개 변형{tree?.auto_style_expand ? ` (확장 ~${n * 3})` : ""}{s.override ? " · 수정됨" : ""}</div>
                      </div>
                      {s.override && <span className="badge warn">수정</span>}
                    </div>
                  );
                }))}
              </div>
            ))}
          </div>
        </div>
      </div>
      <div>
        {slot && field ? (
          <div className="panel highlight">
            <h2>{field.label} › {slot.label} <span className="hint">{msg}</span>
              <span style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
                <button className="small" onClick={reset} disabled={!slot.override}>기본으로</button>
                <button className="small primary" onClick={save} disabled={!dirty}>저장</button>
              </span>
            </h2>
            <div className="muted" style={{ marginBottom: 8 }}>
              한 줄이 한 변형입니다. 쉼표(,)로 끝나면 다음 항목과 이어지는 연결형, 마침표(.)로 끝나면 문장을 닫습니다. 격식체(~합니다/~입니다)로 쓰면 어미 확장이 "~고요,"와 "~어요."를 자동으로 만들어 줍니다.
              <br />자리표시자: {PLACEHOLDERS}
            </div>
            {draft.map((p, i) => (
              <div key={i} className="row" style={{ marginBottom: 6 }}>
                <div><input type="text" value={p} onChange={(e) => { const d = [...draft]; d[i] = e.target.value; setDraft(d); setDirty(true); }} /></div>
                <div className="narrow"><button className="small danger" onClick={() => { setDraft(draft.filter((_, j) => j !== i)); setDirty(true); }}>×</button></div>
              </div>
            ))}
            <div className="row">
              <div className="narrow"><button onClick={() => { setDraft([...draft, ""]); setDirty(true); }}>＋ 변형 추가</button></div>
              <div className="narrow">
                <select value={style} onChange={(e) => setStyle(e.target.value)}>
                  <option value="mixed">혼합</option><option value="casual">구어체</option><option value="formal">격식체</option><option value="chart">기록체</option>
                </select>
              </div>
              <div className="narrow"><button onClick={sample}>🔀 예시 4개 보기</button></div>
            </div>
            {samples.length > 0 && (
              <div className="preview" style={{ minHeight: 60, marginTop: 8 }}>{samples.map((s, i) => `${i + 1}. ${s}`).join("\n")}</div>
            )}
            {field.example && <div className="muted" style={{ marginTop: 6 }}>예시 발화: {field.example}</div>}
          </div>
        ) : (
          <div className="panel muted">
            왼쪽에서 항목을 고르면 그 항목이 발화될 때 쓰이는 모든 말투 변형을 보고 고칠 수 있습니다. 생성 시 변형 중 하나가 무작위로 선택되고, 어미 확장이 켜져 있으면 각 변형이 다시 격식/연결/구어 3가지로 갈라집니다.
            <br /><br />수정 내용은 이 PC의 데이터 폴더(phrases.json)에 저장되며 내보내기/가져오기로 공유할 수 있습니다.
          </div>
        )}
      </div>
    </div>
  );
}
