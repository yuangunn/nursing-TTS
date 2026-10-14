import { AppStatus } from "../lib/onboarding";

export type Tab = "record" | "batch" | "voices" | "results" | "phrases" | "settings";

interface Props {
  tab: Tab;
  onTab: (t: Tab) => void;
  status: AppStatus;
  version: string;
}

/** Left navigation laid out in the order the work actually happens. */
export default function Sidebar({ tab, onTab, status, version }: Props) {
  const flow: { key: Tab; n: number; label: string; sub: string; badge?: string; warn?: boolean }[] = [
    { key: "voices", n: 1, label: "목소리 등록", sub: "간호사 음성 샘플", badge: status.voices ? `${status.voices}개` : undefined, warn: status.checked && status.backendOk && !status.voices },
    { key: "record", n: 2, label: "녹음 만들기", sub: "환자 상태 체크 → 녹음" },
    { key: "batch", n: 3, label: "대량 생성", sub: "가상 환자 N명 자동" },
    { key: "results", n: 4, label: "결과물 · 검수", sub: "듣고 승인, 데이터셋 내보내기", badge: status.recordings ? `${status.recordings}` : undefined },
  ];
  const more: { key: Tab; label: string; icon: string }[] = [
    { key: "phrases", label: "말투 관리", icon: "❝" },
    { key: "settings", label: "설정", icon: "⚙" },
  ];
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="logo" />
        <div>
          <h1>간호기록 음성 녹음 생성기</h1>
          <small>beta {version}</small>
        </div>
      </div>

      <div className="nav-title">작업 순서</div>
      <nav className="nav">
        {flow.map((f) => (
          <button key={f.key} className={tab === f.key ? "active" : ""} onClick={() => onTab(f.key)}>
            <span className="num">{f.n}</span>
            <span className="txt"><span className="l">{f.label}</span><span className="s">{f.sub}</span></span>
            {f.badge && <span className="badge">{f.badge}</span>}
            {f.warn && !f.badge && <span className="badge warn" title="아직 등록된 목소리가 없습니다">없음</span>}
          </button>
        ))}
      </nav>

      <div className="nav-title">그 밖에</div>
      <nav className="nav small">
        {more.map((m) => (
          <button key={m.key} className={tab === m.key ? "active" : ""} onClick={() => onTab(m.key)}>
            <span className="num ic">{m.icon}</span>
            <span className="txt"><span className="l">{m.label}</span></span>
          </button>
        ))}
      </nav>

      <div className="side-status" onClick={() => onTab("settings")} title="클릭하면 설정으로 이동">
        <div><span className={"dot " + (!status.checked ? "" : status.backendOk ? "ok" : "bad")} /> {!status.checked ? "백엔드 확인 중…" : status.backendOk ? "백엔드 실행 중" : status.installed === false ? "백엔드 설치 필요" : "백엔드 꺼짐"}</div>
        {status.backendOk && <div className="muted">엔진: {status.engineLabel}{status.clones ? " · 복제" : status.engineKey ? " · 복제 아님" : ""}</div>}
      </div>
    </aside>
  );
}
