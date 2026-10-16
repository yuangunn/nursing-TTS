import { useEffect, useState } from "react";
import { get, Patient, Scenario } from "../lib/api";
import Term from "./Term";

interface Props {
  patient: Patient;
  onChange: (p: Patient) => void;
  onRandom?: () => void;
  step?: number;
}

/** Patient facts. A chemo admission has a regimen/cycle/day instead of surgery/POD, and its date is the
 *  infusion date (the generator reads ``op_date`` as the treatment date in both cases). */
export default function PatientPanel({ patient, onChange, onRandom, step }: Props) {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  useEffect(() => { get<Scenario[]>("/api/scenarios").then(setScenarios).catch(() => undefined); }, []);
  const chemo = patient.kind === "chemo";
  const set = (k: keyof Patient, v: unknown) => onChange({ ...patient, [k]: v });
  const setKind = (kind: string) => onChange(kind === "chemo"
    ? { ...patient, kind, surgery: "", pod: null, regimen: patient.regimen || "", cycle: patient.cycle ?? 1, day: patient.day ?? 1 }
    : { ...patient, kind: "op", regimen: "", cycle: null, day: null, pod: patient.pod ?? 1 });
  return (
    <div className="panel">
      <h2>
        {step && <span className="step-badge">{step}</span>} 가상 환자 정보 <span className="hint">가명이면 됩니다 · 🎲로 자동 생성</span>
        {onRandom && (
          <button className="small" style={{ marginLeft: "auto" }} onClick={onRandom}>🎲 가상 환자 + 상태 무작위 생성</button>
        )}
      </h2>
      <div className="grid3">
        <div>
          <label>환자 성명 (가명)</label>
          <input type="text" value={patient.name} onChange={(e) => set("name", e.target.value)} />
        </div>
        <div>
          <label>나이</label>
          <input type="number" style={{ width: "100%" }} value={patient.age ?? ""} onChange={(e) => set("age", e.target.value === "" ? null : Number(e.target.value))} />
        </div>
        <div>
          <label>성별</label>
          <select value={patient.sex} onChange={(e) => set("sex", e.target.value)}>
            <option value="남">남</option>
            <option value="여">여</option>
          </select>
        </div>
        <div>
          <label>입원 종류</label>
          <select value={chemo ? "chemo" : "op"} onChange={(e) => setKind(e.target.value)}>
            <option value="op">수술</option>
            <option value="chemo">항암</option>
          </select>
        </div>
        <div style={{ gridColumn: "span 2" }}>
          <label>진단명</label>
          <input type="text" value={patient.diagnosis} onChange={(e) => set("diagnosis", e.target.value)} />
        </div>
        {chemo ? (
          <>
            <div style={{ gridColumn: "span 2" }}>
              <label>항암 regimen (발화 시 병동 읽기로 읽음)</label>
              <input type="text" list="regimens" value={patient.regimen || ""} onChange={(e) => set("regimen", e.target.value)} />
              <datalist id="regimens">{scenarios.filter((s) => s.kind === "chemo").map((s) => <option key={s.key} value={s.key}>{s.ko}</option>)}</datalist>
            </div>
            <div>
              <label><Term k="차수·일차">차수</Term></label>
              <input type="number" min={1} style={{ width: "100%" }} value={patient.cycle ?? ""} onChange={(e) => set("cycle", e.target.value === "" ? null : Number(e.target.value))} />
            </div>
          </>
        ) : (
          <>
            <div style={{ gridColumn: "span 2" }}>
              <label>수술명 (영문, 발화 시 한글/약어로도 읽음)</label>
              <input type="text" list="surgeries" value={patient.surgery} onChange={(e) => set("surgery", e.target.value)} />
              <datalist id="surgeries">{scenarios.filter((s) => s.kind === "op").map((s) => <option key={s.key} value={s.key}>{s.ko}</option>)}</datalist>
            </div>
            <div>
              <label><Term k="POD" /></label>
              <input type="number" min={0} style={{ width: "100%" }} value={patient.pod ?? ""} onChange={(e) => set("pod", e.target.value === "" ? null : Number(e.target.value))} />
            </div>
          </>
        )}
        <div>
          <label>진료과</label>
          <input type="text" value={patient.department} onChange={(e) => set("department", e.target.value)} />
        </div>
        <div>
          <label>담당 교수</label>
          <input type="text" value={patient.professor} onChange={(e) => set("professor", e.target.value)} />
        </div>
        {chemo ? (
          <div>
            <label><Term k="차수·일차">일차 (D)</Term></label>
            <input type="number" min={1} style={{ width: "100%" }} value={patient.day ?? ""} onChange={(e) => set("day", e.target.value === "" ? null : Number(e.target.value))} />
          </div>
        ) : <div />}
        <div>
          <label>{chemo ? "항암 투여일 (예: 10월 14일)" : "수술일 (예: 10월 14일)"}</label>
          <input type="text" value={patient.op_date} onChange={(e) => set("op_date", e.target.value)} />
        </div>
        <div>
          <label>입원일 (예: 10월 13일)</label>
          <input type="text" value={patient.admission_date} onChange={(e) => set("admission_date", e.target.value)} />
        </div>
      </div>
    </div>
  );
}
