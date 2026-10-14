import { Patient, SURGERIES } from "../lib/api";

interface Props {
  patient: Patient;
  onChange: (p: Patient) => void;
  onRandom?: () => void;
}

export default function PatientPanel({ patient, onChange, onRandom }: Props) {
  const set = (k: keyof Patient, v: unknown) => onChange({ ...patient, [k]: v });
  return (
    <div className="panel">
      <h2>
        가상 환자 정보
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
          <label>진단명</label>
          <input type="text" value={patient.diagnosis} onChange={(e) => set("diagnosis", e.target.value)} />
        </div>
        <div style={{ gridColumn: "span 2" }}>
          <label>수술명 (영문, 발화 시 한글/약어로도 읽음)</label>
          <input type="text" list="surgeries" value={patient.surgery} onChange={(e) => set("surgery", e.target.value)} />
          <datalist id="surgeries">
            {SURGERIES.map((s) => (
              <option key={s} value={s} />
            ))}
          </datalist>
        </div>
        <div>
          <label>진료과</label>
          <input type="text" value={patient.department} onChange={(e) => set("department", e.target.value)} />
        </div>
        <div>
          <label>담당 교수</label>
          <input type="text" value={patient.professor} onChange={(e) => set("professor", e.target.value)} />
        </div>
        <div>
          <label>POD</label>
          <input type="number" style={{ width: "100%" }} value={patient.pod ?? ""} onChange={(e) => set("pod", e.target.value === "" ? null : Number(e.target.value))} />
        </div>
        <div>
          <label>수술일 (예: 10월 14일)</label>
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
