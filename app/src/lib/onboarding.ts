/* First-run state and a small app-wide status poller shared by the shell, wizard and guide. */
import { useCallback, useEffect, useState } from "react";
import { get, Voice } from "./api";

const KEY_DONE = "nursing.onboarded";
const KEY_STEP = "nursing.guide.dismissed";

export function isOnboarded(): boolean {
  try { return localStorage.getItem(KEY_DONE) === "1"; } catch { return false; }
}
export function setOnboarded(v: boolean) {
  try { v ? localStorage.setItem(KEY_DONE, "1") : localStorage.removeItem(KEY_DONE); } catch { /* ignore */ }
}
export function isGuideDismissed(): boolean {
  try { return localStorage.getItem(KEY_STEP) === "1"; } catch { return false; }
}
export function setGuideDismissed(v: boolean) {
  try { v ? localStorage.setItem(KEY_STEP, "1") : localStorage.removeItem(KEY_STEP); } catch { /* ignore */ }
}

export interface AppStatus {
  checked: boolean;          // first poll finished
  backendOk: boolean;        // /api/health reachable
  installed: boolean | null; // python env exists (Electron only; null in browser mode)
  engineLabel: string;
  engineKey: string;
  clones: boolean;           // selected engine clones voices
  voices: number;            // voices with ≥1 sample
  voicesTotal: number;
  recordings: number;
}

const EMPTY: AppStatus = { checked: false, backendOk: false, installed: null, engineLabel: "", engineKey: "", clones: false, voices: 0, voicesTotal: 0, recordings: 0 };

/** Polls backend health + a few counts every few seconds; cheap enough to keep alive for the whole session. */
export function useAppStatus(intervalMs = 4000): [AppStatus, () => Promise<void>] {
  const [st, setSt] = useState<AppStatus>(EMPTY);
  const refresh = useCallback(async () => {
    let installed: boolean | null = null;
    try { installed = window.nursing ? await window.nursing.backendInstalled() : null; } catch { installed = null; }
    try {
      await get("/api/health");
      const e = await get<{ selected: string; engines: { key: string; label: string; available: boolean; clones_voice: boolean }[] }>("/api/engines");
      const sel = e.selected === "auto" ? e.engines.find((x) => x.available) : e.engines.find((x) => x.key === e.selected);
      const vs = await get<Voice[]>("/api/voices");
      let recordings = 0;
      try { recordings = (await get<{ rel: string }[]>("/api/recordings?limit=500")).length; } catch { recordings = 0; }
      setSt({
        checked: true, backendOk: true, installed,
        engineLabel: sel ? sel.label : "엔진 없음", engineKey: sel ? sel.key : "", clones: !!sel?.clones_voice,
        voices: vs.filter((v) => v.samples.length).length, voicesTotal: vs.length, recordings,
      });
    } catch {
      setSt((s) => ({ ...s, checked: true, backendOk: false, installed }));
    }
  }, []);
  useEffect(() => {
    let alive = true;
    const tick = async () => { if (alive) await refresh(); };
    tick();
    const id = window.setInterval(tick, intervalMs);
    return () => { alive = false; window.clearInterval(id); };
  }, [refresh, intervalMs]);
  return [st, refresh];
}

export function fmtSec(s: number | null | undefined): string {
  if (s === null || s === undefined || !isFinite(s)) return "—";
  const m = Math.floor(s / 60); const r = Math.round(s % 60);
  return m ? `${m}분 ${r}초` : `${r}초`;
}
