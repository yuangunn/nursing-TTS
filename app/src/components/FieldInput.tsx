import { FieldSchema } from "../lib/api";

interface Props {
  field: FieldSchema;
  value: unknown;
  onChange: (v: unknown) => void;
}

const O2 = ["", "room air", "O2 2L nasal", "O2 3L nasal", "O2 5L mask", "O2 10L mask"];

export default function FieldInput({ field, value, onChange }: Props) {
  const f = field;
  if (f.kind === "select") {
    return (
      <div className="field">
        <label>{f.label}</label>
        <select value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value || undefined)}>
          <option value="">(말하지 않음)</option>
          {f.options.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        {f.example && <div className="example">예: {f.example}</div>}
      </div>
    );
  }
  if (f.kind === "multi") {
    const arr = Array.isArray(value) ? (value as string[]) : [];
    const toggle = (v: string) => {
      let next: string[];
      if (v === "none") next = arr.includes("none") ? [] : ["none"];
      else next = arr.includes(v) ? arr.filter((x) => x !== v) : [...arr.filter((x) => x !== "none"), v];
      onChange(next);
    };
    return (
      <div className="field">
        <label>{f.label}</label>
        <div className="checks">
          {f.options.map((o) => (
            <label key={o.value}>
              <input type="checkbox" checked={arr.includes(o.value)} onChange={() => toggle(o.value)} /> {o.label}
            </label>
          ))}
        </div>
      </div>
    );
  }
  if (f.kind === "number") {
    return (
      <div className="field">
        <label>{f.label}{f.unit ? ` (${f.unit})` : ""}</label>
        <input
          type="number"
          value={value === undefined || value === null ? "" : String(value)}
          min={f.min ?? undefined}
          max={f.max ?? undefined}
          step={f.step ?? 1}
          onChange={(e) => onChange(e.target.value === "" ? undefined : Number(e.target.value))}
        />
        {f.example && <div className="example">예: {f.example}</div>}
      </div>
    );
  }
  if (f.kind === "bool") {
    return (
      <div className="field checks">
        <label>
          <input type="checkbox" checked={!!value} onChange={(e) => onChange(e.target.checked)} /> {f.label}
        </label>
      </div>
    );
  }
  if (f.kind === "vitals") {
    const v = (value as Record<string, unknown>) || {};
    const set = (k: string, val: unknown) => onChange({ ...v, [k]: val });
    const num = (k: string, ph: string, step = 1) => (
      <div>
        <label>{ph}</label>
        <input type="number" step={step} value={v[k] === undefined || v[k] === "" ? "" : String(v[k])}
          onChange={(e) => set(k, e.target.value === "" ? "" : Number(e.target.value))} />
      </div>
    );
    return (
      <div className="field">
        <label>{f.label} <span className="muted">— 비우면 말하지 않음</span></label>
        <div className="vitals">
          {num("sbp", "SBP")}
          {num("dbp", "DBP")}
          {num("hr", "HR")}
          {num("rr", "RR")}
          {num("bt", "BT", 0.1)}
          {num("spo2", "SpO2")}
        </div>
        <div className="row" style={{ marginTop: 6 }}>
          <div>
            <label>산소</label>
            <select value={(v.o2 as string) ?? ""} onChange={(e) => set("o2", e.target.value)}>
              {O2.map((o) => (
                <option key={o} value={o}>{o || "(없음)"}</option>
              ))}
            </select>
          </div>
        </div>
        {f.example && <div className="example">예: {f.example}</div>}
      </div>
    );
  }
  return (
    <div className="field">
      <label>{f.label}</label>
      <input type="text" value={(value as string) ?? ""} placeholder={f.placeholder} onChange={(e) => onChange(e.target.value || undefined)} />
      {f.example && <div className="example">예: {f.example}</div>}
    </div>
  );
}
