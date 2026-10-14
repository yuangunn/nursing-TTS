import { useState } from "react";
import { AppStatus, isGuideDismissed, setGuideDismissed } from "../lib/onboarding";
import { Tab } from "./Sidebar";

interface Props {
  status: AppStatus;
  onTab: (t: Tab) => void;
  onWizard: () => void;
}

/** Persistent "what next" checklist shown above the record page until every step is done or it is dismissed. */
export default function GettingStarted({ status, onTab, onWizard }: Props) {
  const [hidden, setHidden] = useState(isGuideDismissed());
  const steps = [
    { done: status.backendOk, label: "백엔드 설치·실행", hint: status.backendOk ? `엔진: ${status.engineLabel}` : "설정에서 설치하거나 처음 설정을 다시 실행", go: status.backendOk ? undefined : onWizard, goLabel: "처음 설정 열기" },
    { done: status.voices > 0, label: "간호사 목소리 등록", hint: status.voices ? `${status.voices}개 등록됨` : "10초 샘플 3개 권장 · 없어도 시스템 음성으로 체험 가능", go: () => onTab("voices"), goLabel: "목소리 등록" },
    { done: status.recordings > 0, label: "첫 녹음 만들기", hint: status.recordings ? `${status.recordings}개 생성됨` : "아래에서 기록 종류·환자·상태를 고르고 \"녹음 생성\"", go: undefined, goLabel: "" },
    { done: status.recordings > 0 && false, label: "결과물 듣고 검수", hint: "승인/반려 후 데이터셋으로 내보내기", go: status.recordings ? () => onTab("results") : undefined, goLabel: "결과물 보기" },
  ];
  const doneCount = steps.filter((s) => s.done).length;
  if (hidden) return null;
  return (
    <div className="guide">
      <div className="guide-head">
        <b>시작 가이드</b> <span className="muted">{doneCount}/{steps.length} 완료</span>
        <button className="small ghost" style={{ marginLeft: "auto" }} onClick={() => { setGuideDismissed(true); setHidden(true); }}>가이드 숨기기</button>
      </div>
      <ol className="guide-steps">
        {steps.map((s, i) => (
          <li key={i} className={s.done ? "done" : ""}>
            <span className="ico">{s.done ? "✓" : i + 1}</span>
            <div className="txt"><div className="l">{s.label}</div><div className="muted">{s.hint}</div></div>
            {!s.done && s.go && <button className="small" onClick={s.go}>{s.goLabel}</button>}
          </li>
        ))}
      </ol>
    </div>
  );
}
