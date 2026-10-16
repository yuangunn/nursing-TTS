import { Patient } from "./api";

/** A script spec handed from the review page to the record page ("이 대본으로 녹음 만들기"), or the other way
 *  round ("대본 검토에서 열기"). Kept in sessionStorage because pages remount on tab change. */
export interface ScriptHandoff {
  template: string;
  form: Record<string, unknown>;
  patient: Patient;
  datetime: string;
  style: string;
  seed: number | null;
  text_override?: string | null;
}

const KEY = "nursing-tts.script-handoff";

export function setHandoff(h: ScriptHandoff): void {
  try { sessionStorage.setItem(KEY, JSON.stringify(h)); } catch { /* ignore */ }
}

export function takeHandoff(): ScriptHandoff | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    sessionStorage.removeItem(KEY);
    return JSON.parse(raw) as ScriptHandoff;
  } catch {
    return null;
  }
}
