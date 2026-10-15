/* Thin client for the Python backend. */

export interface NursingBridge {
  getBackendUrl(): Promise<string>;
  getBackendLog(): Promise<string>;
  getBackendDir(): Promise<string>;
  openPath(p: string): Promise<string>;
  showInFolder(p: string): Promise<void>;
  chooseDirectory(): Promise<string | null>;
  chooseFile(filters?: { name: string; extensions: string[] }[]): Promise<string | null>;
  restartBackend(): Promise<boolean>;
  backendInstalled(): Promise<boolean>;
  setupBackend(withQwen?: boolean): Promise<{ ok: boolean; message: string }>;
  appVersion(): Promise<string>;
  cancelSetup(): Promise<boolean>;
  checkEnvironment(): Promise<EnvInfo>;
  openExternal(url: string): Promise<void>;
  onSetupProgress(cb: (p: SetupProgress) => void): () => void;
  onBackendReady(cb: (ok: boolean) => void): void;
  onBackendLog(cb: (line: string) => void): void;
}

export interface PythonInfo { found: boolean; version: string; path: string; ok: boolean }
export interface EnvInfo {
  platform: string;
  arch: string;
  appVersion: string;
  python: PythonInfo;
  diskFreeGb: number | null;
  backendInstalled: boolean;
  backendRunning: boolean;
  qwenInstalled: boolean;
  venvDir: string;
  backendDir: string;
  dataDir: string;
}
export type SetupPhase = "venv" | "pip" | "deps" | "qwen" | "model" | "start" | "done" | "error" | "cancelled";
export interface SetupProgress {
  phase: SetupPhase;
  pct: number;
  message: string;
  detail: string;
  elapsed: number;
  eta: number | null;
  withQwen: boolean;
}

declare global {
  interface Window {
    nursing?: NursingBridge;
  }
}

let baseUrl = "http://127.0.0.1:8765";

export async function initApi(): Promise<string> {
  if (window.nursing) {
    try {
      baseUrl = await window.nursing.getBackendUrl();
    } catch {
      /* keep default */
    }
  }
  return baseUrl;
}

export function apiUrl(path: string): string {
  return baseUrl + path;
}

async function handle<T>(r: Response): Promise<T> {
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`;
    try {
      const j = await r.json();
      if (j.detail) msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  return (await r.json()) as T;
}

export async function get<T>(path: string): Promise<T> {
  return handle<T>(await fetch(apiUrl(path)));
}

export async function post<T>(path: string, body?: unknown): Promise<T> {
  return handle<T>(
    await fetch(apiUrl(path), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  );
}

export async function put<T>(path: string, body: unknown): Promise<T> {
  return handle<T>(
    await fetch(apiUrl(path), { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  );
}

export async function patch<T>(path: string, body: unknown): Promise<T> {
  return handle<T>(
    await fetch(apiUrl(path), { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  );
}

export async function del<T>(path: string): Promise<T> {
  return handle<T>(await fetch(apiUrl(path), { method: "DELETE" }));
}

export async function postForm<T>(path: string, form: FormData): Promise<T> {
  return handle<T>(await fetch(apiUrl(path), { method: "POST", body: form }));
}

export async function postBlob(path: string, body: unknown): Promise<{ blob: Blob; headers: Headers }> {
  const r = await fetch(apiUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    let msg = `${r.status}`;
    try {
      msg = (await r.json()).detail || msg;
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  return { blob: await r.blob(), headers: r.headers };
}

/* ---- types mirrored from the backend ---- */

export interface OptionSchema {
  value: string;
  label: string;
}
export interface FieldSchema {
  key: string;
  label: string;
  kind: "select" | "multi" | "number" | "text" | "bool" | "vitals" | "date" | "time";
  options: OptionSchema[];
  unit: string;
  default: unknown;
  min: number | null;
  max: number | null;
  step: number | null;
  hint: string;
  example: string;
  placeholder: string;
}
export interface SectionSchema {
  key: string;
  title: string;
  hint: string;
  group?: string;
  fields: FieldSchema[];
}
export interface TemplateSchema {
  key: string;
  title: string;
  signal_kind: string;
  description: string;
  sections: SectionSchema[];
}
export interface Patient {
  name: string;
  age: number | null;
  sex: string;
  diagnosis: string;
  surgery: string;
  professor: string;
  department: string;
  pod: number | null;
  op_date: string;
  admission_date: string;
  kind?: string;        // op | chemo (항암 입원: 수술 대신 regimen/cycle/day)
  regimen?: string;
  cycle?: number | null;
  day?: number | null;
  scenario?: string;    // clinical.py 시나리오 키
}
export interface NoiseSettings {
  enabled: boolean;
  level: number;
  types: string[];
  density: number;
  reverb: boolean;
}
export interface AugmentSettings {
  enabled: boolean;
  channels: string[];
  speed_min: number;
  speed_max: number;
  speed_prob: number;
  gain_db_range: number;
  clip_prob: number;
}
export const DEFAULT_AUGMENT: AugmentSettings = {
  enabled: false,
  channels: ["studio", "smartphone", "lapel", "recorder"],
  speed_min: 0.92,
  speed_max: 1.08,
  speed_prob: 0.6,
  gain_db_range: 6,
  clip_prob: 0.1,
};
export interface VerifyInfo {
  hyp?: string;
  cer?: number;
  cer_phonetic?: number;
  cer_best?: number;
  threshold?: number;
  passed: boolean | null;
  error?: string;
}
export interface RecordingItem {
  rel: string;
  name: string;
  size: number;
  mtime: number;
  template?: string;
  record_kind?: string;
  patient?: string;
  voice_id?: string;
  voice_name?: string;
  engine?: string;
  duration?: number;
  noise?: boolean;
  channel?: string;
  disfluency?: number;
  review?: string;
  review_note?: string;
  verify?: VerifyInfo | null;
  chunk_verify?: { checked: number; retried: number; still_bad: number; max_cer: number | null } | null;
  signal?: string;
  spoken_text?: string;
  verbatim_text?: string;
  signal_format?: string;
}
export interface ExportReport {
  name: string;
  folder: string;
  total: number;
  total_duration_sec: number;
  counts: { train: number; val: number; test: number };
  skipped: Record<string, number>;
  files: string[];
  speakers: Record<string, { name: string; count: number; duration: number }>;
}
export interface VoiceSample {
  id: string;
  file: string;
  transcript: string;
  script_id: string;
  duration: number;
  created: number;
}
export interface Voice {
  id: string;
  name: string;
  note: string;
  sex: string;
  created: number;
  samples: VoiceSample[];
  primary_sample: string;
}
export interface JobItem {
  index: number;
  status: string;
  patient: string;
  template: string;
  files: Record<string, string>;
  duration: number;
  error: string;
  spoken_text: string;
  verify?: VerifyInfo | null;
}
export interface Job {
  id: string;
  kind: string;
  total: number;
  done: number;
  status: string;
  message: string;
  error: string;
  created: number;
  folder: string;
  items: JobItem[];
}
export interface EngineInfo {
  key: string;
  label: string;
  available: boolean;
  status: string;
  clones_voice: boolean;
}
export interface Settings {
  tts_engine: string;
  device: string;
  qwen_model: string;
  qwen_idle_unload_min: number;
  http_tts_url: string;
  output_dir: string;
  sample_rate: number;
  llm_provider: string;
  llm_api_key: string;
  llm_api_key_set: boolean;
  llm_model: string;
  llm_base_url: string;
  default_style: string;
  noise_default_level: number;
  floor_dbfs: number;        // 항상 깔리는 바닥 소음 (dBFS, 0 = 없음)
  room_wet: number;          // 항상 적용되는 약한 울림 (0 = 없음)
  asr_verify: boolean;
  asr_model: string;
  asr_device: string;
  cer_threshold: number;
  chunk_cer_threshold: number;   // 문장 조각 되읽기 CER 기준 (초과 시 재합성)
  chunk_retries: number;
  loudness_dbfs: number;
  default_disfluency: number;
  auto_style_expand: boolean;
  signal_format: string;
  signal_aliases: boolean;
  rounds_shift: Record<string, number>;   // 회진 대화: 역할별 반음 (doctor/patient/nurse)
  rounds_tempo: Record<string, number>;   // 회진 대화: 역할별 말속도 (1 = 등록 목소리 속도)
  rounds_tempo_jitter: number;
  _output_dir_resolved: string;
  _data_dir: string;
}
export interface NoiseCatalogItem {
  key: string;
  label: string;
  builtin: boolean;
  continuous: boolean;
  duration?: number;
}
export interface EnrollScript {
  id: string;
  title: string;
  text: string;
}

export const DEFAULT_PATIENT: Patient = {
  name: "홍길동",
  age: 64,
  sex: "남",
  diagnosis: "위암",
  surgery: "Laparoscopic total gastrectomy",
  professor: "김민수",
  department: "외과",
  pod: 2,
  op_date: "10월 14일",
  admission_date: "10월 13일",
};

export const DEFAULT_NOISE: NoiseSettings = {
  enabled: false,
  level: 35,
  types: ["room_tone", "monitor_pulse", "crowd_babble", "footsteps"],
  density: 4,
  reverb: false,
};

export const SURGERIES = [
  "Laparoscopic total gastrectomy",
  "Laparoscopic subtotal gastrectomy",
  "Laparoscopic distal gastrectomy",
  "Laparoscopic right hemicolectomy",
  "Laparoscopic anterior resection",
  "Laparoscopic low anterior resection",
  "Laparoscopic cholecystectomy",
  "Laparoscopic appendectomy",
  "Open hemicolectomy",
  "Lobectomy",
  "Mastectomy",
  "Total knee replacement arthroplasty",
  "Total hip replacement arthroplasty",
  "Hysterectomy",
  "PPPD",
  "Hepatectomy",
  "Thyroidectomy",
];

export function nowLocalIso(): string {
  const d = new Date();
  d.setSeconds(0, 0);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
