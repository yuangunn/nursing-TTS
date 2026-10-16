import { useEffect, useRef, useState } from "react";
import Scene from "./components/Scene";
import Sidebar, { Tab } from "./components/Sidebar";
import SetupWizard from "./components/SetupWizard";
import GettingStarted from "./components/GettingStarted";
import InstallProgress from "./components/InstallProgress";
import { initApi, UpdateInfo } from "./lib/api";
import { isOnboarded, useAppStatus } from "./lib/onboarding";
import RecordPage from "./pages/RecordPage";
import ScriptReviewPage from "./pages/ScriptReviewPage";
import ImportPage from "./pages/ImportPage";
import VoicesPage from "./pages/VoicesPage";
import BatchPage from "./pages/BatchPage";
import SettingsPage from "./pages/SettingsPage";
import ResultsPage from "./pages/ResultsPage";
import PhrasesPage from "./pages/PhrasesPage";
import { EnergyContext } from "./lib/energy";

const TITLES: Record<Tab, { t: string; d: string }> = {
  voices: { t: "1 · 목소리 등록", d: "간호사 목소리 샘플을 녹음하거나 파일로 올립니다. 10초짜리 3개면 충분합니다." },
  record: { t: "3 · 녹음 만들기", d: "기록 종류와 가상 환자, 상태를 고르면 대본이 바로 만들어지고, 버튼 하나로 녹음·정답 텍스트가 저장됩니다." },
  batch: { t: "3 · 대량 생성", d: "가상 환자를 자동으로 만들어 녹음을 한꺼번에 생성합니다." },
  results: { t: "4 · 결과물 · 검수", d: "생성된 녹음을 듣고 승인/반려한 뒤 학습용 데이터셋으로 내보냅니다." },
  phrases: { t: "말투 관리", d: "요소별 말투 변형을 보고 고치거나 추가합니다." },
  settings: { t: "설정", d: "음성 엔진, 저장 위치, 백엔드 설치 상태." },
  import: { t: "표 데이터 가져오기", d: "CSV·엑셀 표의 열을 환자 정보·체크 항목에 연결하고 셀 값의 뜻을 정해 행마다 대본과 녹음을 만듭니다." },
  review: { t: "2 · 대본 생성", d: "무작위 대본을 여러 개 읽고 병동에서 쓰지 않는 문장을 표시합니다. 표시한 문장은 말투·문구 풀 수정에 씁니다." },
};

export default function App() {
  const [tab, setTab] = useState<Tab>("record");
  const [update, setUpdate] = useState<UpdateInfo | null>(null);
  useEffect(() => window.nursing?.onUpdateAvailable((info) => setUpdate(info)), []);
  const skipUpdate = async () => { if (update) await window.nursing?.setUpdateSettings({ skipVersion: update.latest }); setUpdate(null); };
  const [ready, setReady] = useState(false);
  const [wizard, setWizard] = useState(false);
  const [version, setVersion] = useState("");
  const [energy, setEnergy] = useState(0);
  const [status, refresh] = useAppStatus();
  // A page that mounted while the backend was unreachable fetched nothing (noise list, voices, templates …).
  // Remount it once the backend answers; pages mounted with the backend up keep their state.
  const [epoch, setEpoch] = useState(0);
  const staleRef = useRef(false);
  useEffect(() => { staleRef.current = !status.checked || !status.backendOk; }, [tab]);   // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (status.backendOk && staleRef.current) { staleRef.current = false; setEpoch((e) => e + 1); }
  }, [status.backendOk]);

  useEffect(() => {
    (async () => {
      await initApi();
      try { setVersion(window.nursing ? await window.nursing.appVersion() : "dev"); } catch { setVersion(""); }
      setWizard(!isOnboarded());
      setReady(true);
    })();
    const open = () => setWizard(true);
    window.addEventListener("nursing:wizard", open);
    return () => window.removeEventListener("nursing:wizard", open);
  }, []);

  if (!ready) return <div className="boot"><div className="logo" /><div>불러오는 중…</div></div>;

  if (wizard) {
    return (
      <>
        <Scene energy={0.2} />
        <SetupWizard status={status} refresh={refresh} onFinish={(goto) => { setWizard(false); setTab(goto); refresh(); }} />
      </>
    );
  }

  const title = TITLES[tab];
  const backendDown = status.checked && !status.backendOk;

  return (
    <EnergyContext.Provider value={setEnergy}>
      <Scene energy={energy} />
      <div className="shell">
        <Sidebar tab={tab} onTab={setTab} status={status} version={version} />
        <div className="main">
          <div className="page-head">
            <div>
              <h2>{title.t}</h2>
              <div className="muted">{title.d}</div>
            </div>
            <button className="ghost small" onClick={() => setWizard(true)} title="처음 설정 마법사를 다시 엽니다">? 도움말 · 처음 설정</button>
          </div>
          <div className="content">
            {update && (
              <div className="callout" style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                <div><b>새 버전 v{update.latest}</b>이 있습니다 (지금 v{update.current}). {update.published ? `${new Date(update.published).toLocaleDateString()} 공개` : ""}</div>
                <div className="narrow"><button className="primary small" onClick={() => window.nursing?.openExternal(update.url)}>다운로드 페이지 열기</button></div>
                <div className="narrow"><button className="small" onClick={skipUpdate} title="이 버전은 다시 알리지 않습니다 (설정에서 되돌릴 수 있음)">이 버전 알림 받지 않기</button></div>
                <div className="narrow"><button className="ghost small" onClick={() => setUpdate(null)}>나중에</button></div>
              </div>
            )}
            {backendDown && tab !== "settings" && (
              <div className="callout bad backend-down">
                <div>
                  <b>백엔드가 꺼져 있습니다.</b> {status.installed === false ? "아직 설치되지 않았습니다. 아래에서 설치하면 자동으로 켜집니다." : "재시작해 보고, 계속 안 되면 설정의 로그를 확인하세요."}
                </div>
                {status.installed === false ? (
                  <InstallProgress withQwen={false} compact onDone={() => refresh()} />
                ) : (
                  <div className="row" style={{ marginTop: 8 }}>
                    <div className="narrow"><button className="primary" onClick={async () => { await window.nursing?.restartBackend(); refresh(); }}>백엔드 재시작</button></div>
                    <div className="narrow"><button onClick={() => setTab("settings")}>설정·로그 보기</button></div>
                  </div>
                )}
              </div>
            )}
            {tab === "record" && !backendDown && <GettingStarted status={status} onTab={setTab} onWizard={() => setWizard(true)} />}
            <div key={`${tab}:${epoch}`} className="fade-in">
              {tab === "record" && <RecordPage status={status} onTab={setTab} />}
              {tab === "review" && <ScriptReviewPage onTab={setTab} />}
              {tab === "batch" && <BatchPage />}
              {tab === "import" && <ImportPage />}
              {tab === "voices" && <VoicesPage />}
              {tab === "results" && <ResultsPage />}
              {tab === "phrases" && <PhrasesPage />}
              {tab === "settings" && <SettingsPage />}
            </div>
          </div>
        </div>
      </div>
    </EnergyContext.Provider>
  );
}
