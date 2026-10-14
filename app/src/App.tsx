import { useEffect, useState } from "react";
import Scene from "./components/Scene";
import { get, initApi } from "./lib/api";
import RecordPage from "./pages/RecordPage";
import VoicesPage from "./pages/VoicesPage";
import BatchPage from "./pages/BatchPage";
import SettingsPage from "./pages/SettingsPage";
import ResultsPage from "./pages/ResultsPage";
import { EnergyContext } from "./lib/energy";

type Tab = "record" | "voices" | "batch" | "results" | "settings";

export default function App() {
  const [tab, setTab] = useState<Tab>("record");
  const [backendOk, setBackendOk] = useState<boolean | null>(null);
  const [engine, setEngine] = useState<string>("");
  const [energy, setEnergy] = useState(0);

  useEffect(() => {
    let alive = true;
    let id: number | undefined;
    (async () => {
      await initApi();
      const check = async () => {
        try {
          await get("/api/health");
          const e = await get<{ selected: string; engines: { key: string; label: string; available: boolean }[] }>("/api/engines");
          if (!alive) return;
          setBackendOk(true);
          const sel = e.selected === "auto" ? e.engines.find((x) => x.available) : e.engines.find((x) => x.key === e.selected);
          setEngine(sel ? sel.label : "엔진 없음");
        } catch {
          if (alive) setBackendOk(false);
        }
      };
      check();
      id = window.setInterval(check, 5000);
    })();
    return () => {
      alive = false;
      if (id) window.clearInterval(id);
    };
  }, []);

  const tabs: { key: Tab; label: string; icon: string }[] = [
    { key: "record", label: "녹음 생성", icon: "◉" },
    { key: "batch", label: "대량 생성", icon: "⧉" },
    { key: "voices", label: "목소리 등록", icon: "♪" },
    { key: "results", label: "결과물·QA", icon: "✓" },
    { key: "settings", label: "설정", icon: "⚙" },
  ];

  return (
    <EnergyContext.Provider value={setEnergy}>
      <Scene energy={energy} />
      <div className="app">
        <div className="topbar">
          <div className="brand">
            <div className="logo" />
            <div>
              <h1>간호기록 음성 녹음 생성기</h1>
              <small>Nursing Narrative · Voice Studio</small>
            </div>
          </div>
          <nav className="tabs">
            {tabs.map((t) => (
              <button key={t.key} className={tab === t.key ? "active" : ""} onClick={() => setTab(t.key)}>
                <span style={{ marginRight: 6, opacity: 0.8 }}>{t.icon}</span>{t.label}
              </button>
            ))}
          </nav>
          <div className="status">
            <span className={"dot " + (backendOk === null ? "" : backendOk ? "ok" : "bad")} />
            {backendOk === null ? "백엔드 연결 중…" : backendOk ? `연결됨 · ${engine}` : "백엔드 연결 안 됨 (설정 탭에서 로그 확인)"}
          </div>
        </div>
        <div className="content">
          <div key={tab} className="fade-in">
            {tab === "record" && <RecordPage />}
            {tab === "batch" && <BatchPage />}
            {tab === "voices" && <VoicesPage />}
            {tab === "results" && <ResultsPage />}
            {tab === "settings" && <SettingsPage />}
          </div>
        </div>
      </div>
    </EnergyContext.Provider>
  );
}
