import { useState } from "react";
import FieldInput from "./FieldInput";
import { TemplateSchema } from "../lib/api";

interface Props {
  template: TemplateSchema | undefined;
  form: Record<string, unknown>;
  onChange: (next: Record<string, unknown>) => void;
  step?: number;
}

/** The record's check items (and, for the progress record, the charting checklist) as collapsible sections. */
export default function FormSections({ template, form, onChange, step }: Props) {
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const setField = (key: string, v: unknown) => onChange({ ...form, [key]: v });
  const render = (s: TemplateSchema["sections"][number], protocol = false) => {
    const isCollapsed = collapsed[s.key] ?? protocol;
    const checked = protocol ? s.fields.filter((f) => f.kind === "bool" && form[f.key]).length : 0;
    return (
      <div className="section" key={s.key}>
        <div className="section-head" onClick={() => setCollapsed((c) => ({ ...c, [s.key]: !isCollapsed }))}>
          <strong>{isCollapsed ? "▸" : "▾"} {s.title}<span className="hint">{s.hint}</span></strong>
          {protocol && checked > 0 && <span className="badge ok">{checked}개 체크</span>}
        </div>
        {!isCollapsed && (
          <div className={s.fields.length > 3 ? "grid2" : ""}>
            {s.fields.map((f) => <FieldInput key={f.key} field={f} value={form[f.key]} onChange={(v) => setField(f.key, v)} />)}
          </div>
        )}
      </div>
    );
  };
  const protocols = template?.sections.filter((s) => s.group === "protocol") ?? [];
  return (
    <>
      <div className="panel">
        <h2>{step && <span className="step-badge">{step}</span>} 환자 상태 체크 <span className="hint">체크/선택한 항목만 발화됩니다 · 비워 두면 기본 상태로 읽습니다</span></h2>
        {template?.sections.filter((s) => s.group !== "protocol").map((s) => render(s))}
      </div>
      {protocols.length > 0 && (
        <div className="panel">
          <h2>{step && <span className="step-badge">{step + 1}</span>} 간호 프로토콜 체크리스트 <span className="hint">정규 차팅 · 간호진단별 중재 항목, 체크한 항목이 "~함" 기록체 또는 선택한 말투로 발화됩니다</span>
            <span style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
              <button className="small" onClick={() => setCollapsed((c) => { const n = { ...c }; protocols.forEach((x) => { n[x.key] = false; }); return n; })}>모두 펼치기</button>
              <button className="small" onClick={() => setCollapsed((c) => { const n = { ...c }; protocols.forEach((x) => { n[x.key] = true; }); return n; })}>모두 접기</button>
              <button className="small danger" onClick={() => { const n = { ...form }; protocols.forEach((x) => x.fields.forEach((f) => { if (f.kind === "bool") delete n[f.key]; })); onChange(n); }}>체크 해제</button>
            </span>
          </h2>
          {protocols.map((s) => render(s, true))}
        </div>
      )}
    </>
  );
}
