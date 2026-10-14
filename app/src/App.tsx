import { useEffect, useState } from "react";
import { get, initApi } from "./lib/api";
import RecordPage from "./pages/RecordPage";
import VoicesPage from "./pages/VoicesPage";
import BatchPage from "./pages/BatchPage";
import SettingsPage from "./pages/SettingsPage";

type Tab = "record" | "voices" | "batch" | "settings";

export default function App() {
  const [tab, setTab] = useState<Tab>("record");
  const [backendOk, setBackendOk] = useState<boolean | null>(null);
  const [engine, setEngine] = useState<string>("");

  useEffect(() => {
    let alive = true;
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
      const id = setInterval(check, 5000);
      return () => clearInterval(id);
    })();
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div className="app">
      <div className="topbar">
        <h1>간호기록 음성 녹음 생성기</h1>
        <nav className="tabs">
          <button className={tab === "record" ? "active" : ""} onClick={() => setTab("record")}>녹음 생성</button>
          <button className={tab === "batch" ? "active" : ""} onClick={() => setTab("batch")}>대량 생성</button>
          <button className={tab === "voices" ? "active" : ""} onClick={() => setTab("voices")}>목소리 등록</button>
          <button className={tab === "settings" ? "active" : ""} onClick={() => setTab("settings")}>설정</button>
        </nav>
        <div className="status">
          <span className={"dot " + (backendOk === null ? "" : backendOk ? "ok" : "bad")} />
          {backendOk === null ? "백엔드 연결 중…" : backendOk ? `백엔드 연결됨 · ${engine}` : "백엔드 연결 안 됨 (설정 탭에서 로그 확인)"}
        </div>
      </div>
      <div className="content">
        {tab === "record" && <RecordPage />}
        {tab === "batch" && <BatchPage />}
        {tab === "voices" && <VoicesPage />}
        {tab === "settings" && <SettingsPage />}
      </div>
    </div>
  );
}
