import { useEffect, useState } from "react";
import Term from "./Term";
import { get } from "../lib/api";

interface Fmt { key: string; label: string; written: string }

interface Props {
  value: string;              // "" = 설정 기본값, "random", or a key
  onChange: (v: string) => void;
  allowDefault?: boolean;
  aliases?: boolean | null;
  onAliases?: (v: boolean) => void;
}

export default function SignalSelect({ value, onChange, allowDefault = true, aliases, onAliases }: Props) {
  const [fmts, setFmts] = useState<Fmt[]>([]);
  const [custom, setCustom] = useState<string[]>([]);
  const [def, setDef] = useState("strict");
  useEffect(() => {
    get<{ formats: Fmt[]; custom: string[]; default: string }>("/api/signal/formats").then((r) => {
      setFmts(r.formats);
      setCustom(r.custom);
      setDef(r.default);
    }).catch(() => undefined);
  }, []);
  return (
    <div className="row" style={{ marginBottom: 0 }}>
      <div>
        <label><Term k="시그널" />(녹음 시작 문장) 형식</label>
        <select value={value} onChange={(e) => onChange(e.target.value)}>
          {allowDefault && <option value="">설정 기본값 ({fmts.find((f) => f.key === def)?.label || def})</option>}
          <option value="random">무작위 혼합 (필수 형식 40% + 변형들{custom.length ? ` + 내 형식 ${custom.length}개` : ""})</option>
          {fmts.map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}
          {custom.map((c) => <option key={c} value={c}>내 형식: {c}</option>)}
        </select>
      </div>
      {onAliases && (
        <div className="narrow">
          <label style={{ color: "inherit", fontSize: 13 }} title="간호정보조사지, 퇴원 교육, 수술 전 교육, 인수인계 같은 비슷한 표현을 시그널의 기록종류 자리에 가끔 사용">
            <input type="checkbox" checked={!!aliases} onChange={(e) => onAliases(e.target.checked)} /> 기록종류 유사 표현 섞기
          </label>
        </div>
      )}
    </div>
  );
}
