import { app, BrowserWindow, dialog, ipcMain, shell } from "electron";
import { ChildProcess, execFile, spawn } from "child_process";
import * as fs from "fs";
import * as http from "http";
import * as path from "path";

const BACKEND_PORT = Number(process.env.NURSING_TTS_PORT || 8765);
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;
const DEV_URL = process.env.VITE_DEV_SERVER_URL;

let backend: ChildProcess | null = null;
let mainWindow: BrowserWindow | null = null;
let backendLog: string[] = [];

function backendDir(): string {
  // dev: <repo>/app/dist-electron/main.js -> <repo>/backend ; prod: resources/backend
  if (app.isPackaged) return path.join(process.resourcesPath, "backend");
  return path.resolve(__dirname, "..", "..", "backend");
}

function venvDir(): string {
  // Packaged apps cannot write inside their bundle, so the Python env lives in userData.
  return path.join(app.getPath("userData"), "venv");
}

function venvPython(dir: string): string {
  return process.platform === "win32" ? path.join(dir, "Scripts", "python.exe") : path.join(dir, "bin", "python");
}

function findPython(dir: string): string | null {
  const candidates = [venvPython(venvDir()), venvPython(path.join(dir, ".venv"))];
  for (const c of candidates) if (fs.existsSync(c)) return c;
  return null;
}

function systemPythonCandidates(): string[] {
  if (process.platform === "win32") return ["py", "python", "python3"];
  return ["python3.12", "python3.11", "python3.10", "python3", "/opt/homebrew/bin/python3", "/usr/local/bin/python3", "/usr/bin/python3"];
}

function backendInstalled(): boolean {
  return findPython(backendDir()) !== null;
}

/* ---------------- first-run environment check ---------------- */

export interface PythonInfo { found: boolean; version: string; path: string; ok: boolean }

function pyVersion(cmd: string): Promise<PythonInfo> {
  return new Promise((resolve) => {
    const args = cmd === "py" ? ["-3", "--version"] : ["--version"];
    const child = execFile(cmd, args, { timeout: 8000, windowsHide: true, shell: process.platform === "win32" }, (err, stdout, stderr) => {
      if (err) return resolve({ found: false, version: "", path: cmd, ok: false });
      const m = /Python\s+(\d+)\.(\d+)(?:\.(\d+))?/.exec(String(stdout) + String(stderr));
      if (!m) return resolve({ found: false, version: "", path: cmd, ok: false });
      const major = Number(m[1]); const minor = Number(m[2]);
      resolve({ found: true, version: `${m[1]}.${m[2]}${m[3] ? "." + m[3] : ""}`, path: cmd, ok: major > 3 || (major === 3 && minor >= 10) });
    });
    child.on("error", () => resolve({ found: false, version: "", path: cmd, ok: false }));
  });
}

async function findSystemPython(): Promise<PythonInfo> {
  let best: PythonInfo = { found: false, version: "", path: "", ok: false };
  for (const c of systemPythonCandidates()) {
    const info = await pyVersion(c);
    if (info.ok) return info;
    if (info.found && !best.found) best = info;
  }
  return best;
}

/** Version of the python inside an existing venv ("" if missing/unreadable). */
function venvPyVersion(venv: string): Promise<PythonInfo> {
  const py = venvPython(venv);
  if (!fs.existsSync(py)) return Promise.resolve({ found: false, version: "", path: py, ok: false });
  return pyVersion(py);
}

function f5Installed(): boolean {
  const venv = venvDir();
  try {
    const lib = process.platform === "win32" ? path.join(venv, "Lib", "site-packages") : path.join(venv, "lib");
    if (!fs.existsSync(lib)) return false;
    const dirs = process.platform === "win32" ? [lib] : fs.readdirSync(lib).map((d) => path.join(lib, d, "site-packages"));
    return dirs.some((d) => fs.existsSync(path.join(d, "f5_tts")));
  } catch { return false; }
}

async function checkEnvironment() {
  const python = await findSystemPython();
  let diskFreeGb: number | null = null;
  try {
    const st = fs.statfsSync(app.getPath("userData"));
    diskFreeGb = Math.round(((st.bavail * st.bsize) / 1e9) * 10) / 10;
  } catch { diskFreeGb = null; }
  return {
    platform: process.platform,
    arch: process.arch,
    appVersion: app.getVersion(),
    python,
    diskFreeGb,
    backendInstalled: backendInstalled(),
    backendRunning: await ping(BACKEND_URL),
    f5Installed: f5Installed(),
    venvDir: venvDir(),
    backendDir: backendDir(),
    dataDir: app.getPath("userData"),
  };
}

/* ---------------- backend installer with structured progress ---------------- */

type Phase = "venv" | "pip" | "deps" | "f5" | "start" | "done" | "error" | "cancelled";
interface SetupProgress { phase: Phase; pct: number; message: string; detail: string; elapsed: number; eta: number | null; withF5: boolean }

// Typical durations (seconds) on a normal broadband connection — used for the ETA only.
const EXPECTED: Record<string, number> = { venv: 10, pip: 15, deps: 90, f5: 720, start: 12 };
const EXPECTED_PKGS = { deps: 32, f5: 70 };

let setupChild: ChildProcess | null = null;
let setupCancelled = false;

/** Create the venv in userData and install the backend requirements, reporting phase/percent/ETA to the renderer. */
async function setupBackend(withF5 = false): Promise<{ ok: boolean; message: string }> {
  const dir = backendDir();
  const venv = venvDir();
  const t0 = Date.now();
  const phases: Phase[] = withF5 ? ["venv", "pip", "deps", "f5", "start"] : ["venv", "pip", "deps", "start"];
  const totalExpected = phases.reduce((a, p) => a + EXPECTED[p], 0);
  let phaseIdx = 0;
  let phaseStart = t0;
  let inner = 0; // 0..1 within the current phase
  setupCancelled = false;
  let backtracked = "";

  const emit = (phase: Phase, message: string, detail = "") => {
    const doneBefore = phases.slice(0, phaseIdx).reduce((a, p) => a + EXPECTED[p], 0);
    const cur = phases[phaseIdx] ? EXPECTED[phases[phaseIdx]] : 0;
    const pct = phase === "done" ? 100 : Math.min(99, Math.round(((doneBefore + cur * inner) / totalExpected) * 100));
    const elapsed = (Date.now() - t0) / 1000;
    const phaseElapsed = (Date.now() - phaseStart) / 1000;
    const remainingCur = Math.max(cur * 0.15, cur * (1 - inner) - Math.max(0, phaseElapsed - cur * inner));
    const remainingNext = phases.slice(phaseIdx + 1).reduce((a, p) => a + EXPECTED[p], 0);
    const eta = phase === "done" || phase === "error" ? 0 : Math.round(remainingCur + remainingNext);
    const p: SetupProgress = { phase, pct, message, detail, elapsed: Math.round(elapsed), eta, withF5 };
    mainWindow?.webContents.send("setup-progress", p);
  };
  const nextPhase = () => { phaseIdx++; phaseStart = Date.now(); inner = 0; };

  const run = (cmd: string, args: string[], cwd: string, onLine?: (l: string) => void) =>
    new Promise<number>((resolve) => {
      pushLog(`[setup] $ ${cmd} ${args.join(" ")}`);
      const child = spawn(cmd, args, { cwd, env: { ...process.env, PYTHONUTF8: "1", PIP_DISABLE_PIP_VERSION_CHECK: "1", PIP_PROGRESS_BAR: "off" }, windowsHide: true, shell: process.platform === "win32" });
      setupChild = child;
      const feed = (d: unknown) => {
        const text = String(d);
        pushLog(text);
        if (onLine) text.split(/\r?\n/).forEach((l) => l.trim() && onLine(l.trim()));
      };
      child.stdout?.on("data", feed);
      child.stderr?.on("data", feed);
      child.on("error", (e) => { pushLog(`[setup] ${e.message}`); resolve(-1); });
      child.on("exit", (code) => { setupChild = null; resolve(code ?? -1); });
    });

  /** Parse pip output into a 0..1 progress for the phase. */
  const pipTracker = (expectedPkgs: number) => {
    let collected = 0; let installingTotal = 0;
    const seen = new Map<string, number>();
    return (line: string) => {
      if (/^Collecting /.test(line)) {
        collected++; inner = Math.min(0.6, (collected / expectedPkgs) * 0.6);
        const name = line.replace(/^Collecting /, "").split(/[<>=!~ (]/)[0].toLowerCase();
        const n = (seen.get(name) || 0) + 1; seen.set(name, n);
        if (n > 40) {
          // pip is backtracking through old releases; this never finishes in reasonable time.
          pushLog(`[setup] resolver is backtracking on ${name} (${n} candidates) — aborting`);
          backtracked = name; setupChild?.kill();
          return;
        }
        emit(phases[phaseIdx], phaseLabel(), n > 5 ? `${name} 버전 충돌을 푸는 중 (${n}번째 시도)… 오래 걸리면 자동으로 중단합니다` : line.replace(/^Collecting /, "받는 중: "));
      }
      else if (/^Downloading /.test(line)) { emit(phases[phaseIdx], phaseLabel(), line.replace(/^Downloading /, "다운로드: ")); }
      else if (/^Installing collected packages/.test(line)) { installingTotal = line.split(":")[1]?.split(",").length || 0; inner = Math.max(inner, 0.7); emit(phases[phaseIdx], phaseLabel(), `패키지 ${installingTotal}개 설치 중…`); }
      else if (/^Successfully installed/.test(line)) { inner = 1; emit(phases[phaseIdx], phaseLabel(), "설치 완료"); }
      else if (/^Requirement already satisfied/.test(line)) { collected++; inner = Math.min(0.6, (collected / expectedPkgs) * 0.6); }
      else if (/error/i.test(line) && !/^WARNING/.test(line)) { emit(phases[phaseIdx], phaseLabel(), line.slice(0, 160)); }
    };
  };
  const phaseLabel = () => ({ venv: "Python 가상환경 만드는 중", pip: "pip 업데이트 중", deps: "백엔드 패키지 설치 중", f5: "F5-TTS + PyTorch 설치 중 (수 GB, 오래 걸립니다)", start: "백엔드 시작 중", done: "완료", error: "오류", cancelled: "취소됨" }[phases[phaseIdx] || "done"]);
  const fail = (message: string) => { emit("error", message); return { ok: false, message }; };
  const checkCancel = () => setupCancelled;

  // phase: venv
  emit("venv", phaseLabel());
  if (fs.existsSync(venvPython(venv))) {
    const existing = await venvPyVersion(venv);
    if (!existing.ok) {
      pushLog(`[setup] existing venv uses Python ${existing.version || "?"} (< 3.10) — recreating`);
      emit("venv", phaseLabel(), `기존 환경이 Python ${existing.version || "?"}라서 다시 만듭니다 (3.10 이상 필요)`);
      backend?.kill(); backend = null;
      try { fs.rmSync(venv, { recursive: true, force: true }); } catch (e) { return fail(`이전 환경을 지우지 못했습니다: ${String(e)}`); }
    }
  }
  if (!fs.existsSync(venvPython(venv))) {
    const py = await findSystemPython();
    if (!py.ok) return fail(py.found ? `Python ${py.version}은 너무 낮습니다. 3.10 이상이 필요합니다.` : "Python 3.10 이상을 찾지 못했습니다. python.org 또는 Homebrew(brew install python)로 설치한 뒤 다시 시도하세요.");
    const args = py.path === "py" ? ["-3", "-m", "venv", venv] : ["-m", "venv", venv];
    inner = 0.3; emit("venv", phaseLabel(), `${py.path} (Python ${py.version})`);
    if ((await run(py.path, args, dir)) !== 0 || !fs.existsSync(venvPython(venv))) return fail("가상환경 생성에 실패했습니다 (로그 확인).");
  }
  if (checkCancel()) return fail("취소됨");
  nextPhase();
  const py = venvPython(venv);
  // phase: pip
  emit("pip", phaseLabel());
  if ((await run(py, ["-m", "pip", "install", "--upgrade", "pip"], dir, pipTracker(1))) !== 0) return fail("pip 업그레이드 실패 (인터넷 연결을 확인하세요).");
  if (checkCancel()) return fail("취소됨");
  nextPhase();
  // phase: deps
  emit("deps", phaseLabel());
  if ((await run(py, ["-m", "pip", "install", "-r", path.join(dir, "requirements.txt")], dir, pipTracker(EXPECTED_PKGS.deps))) !== 0) return fail("백엔드 패키지 설치 실패 (인터넷 연결 또는 로그 확인).");
  if (checkCancel()) return fail("취소됨");
  nextPhase();
  // phase: f5 (optional)
  if (withF5) {
    emit("f5", phaseLabel(), "1/2 PyTorch 받는 중 (가장 큰 파일, 수 분)");
    const common = ["--prefer-binary", "-c", path.join(dir, "constraints-f5.txt")];
    if ((await run(py, ["-m", "pip", "install", ...common, "torch>=2.3", "torchaudio>=2.3"], dir, pipTracker(12))) !== 0) return fail("PyTorch 설치 실패 (로그 확인). 기본 백엔드는 설치되어 있으니 앱은 쓸 수 있습니다.");
    if (checkCancel()) return fail("취소됨");
    inner = Math.max(inner, 0.5);
    emit("f5", phaseLabel(), "2/2 F5-TTS 패키지 설치 중");
    const code = await run(py, ["-m", "pip", "install", ...common, "-r", path.join(dir, "requirements-f5.txt")], dir, pipTracker(EXPECTED_PKGS.f5));
    if (backtracked) return fail(`pip이 '${backtracked}' 패키지 버전 충돌을 풀지 못해 중단했습니다. Python 버전(3.10~3.13 권장)을 확인하고 다시 시도하세요. 기본 백엔드는 설치되어 있어 앱은 쓸 수 있습니다.`);
    if (code !== 0) return fail("F5-TTS 설치 실패 (로그 확인). 기본 백엔드는 설치되어 있으니 앱은 쓸 수 있습니다.");
    if (checkCancel()) return fail("취소됨");
    nextPhase();
  }
  // phase: start
  emit("start", phaseLabel());
  backend?.kill();
  backend = null;
  await startBackend();
  const up = await ping(BACKEND_URL);
  if (!up) return fail("백엔드가 시작되지 않았습니다 (로그 확인).");
  nextPhase();
  emit("done", "설치 완료", venv);
  return { ok: true, message: `백엔드 설치 완료: ${venv}` };
}

function ping(url: string): Promise<boolean> {
  return new Promise((resolve) => {
    const req = http.get(url + "/api/health", (res) => {
      resolve((res.statusCode || 500) < 500);
      res.resume();
    });
    req.on("error", () => resolve(false));
    req.setTimeout(1500, () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function startBackend(): Promise<void> {
  if (await ping(BACKEND_URL)) {
    backendLog.push("[main] backend already running");
    return;
  }
  const dir = backendDir();
  const py = findPython(dir);
  if (!py) {
    pushLog("[main] 백엔드 Python 환경이 없습니다. 설정 탭에서 '백엔드 설치'를 실행하세요.");
    return;
  }
  const env = { ...process.env, PYTHONUTF8: "1", PYTHONIOENCODING: "utf-8" };
  backend = spawn(py, ["-m", "nursing_tts", "--port", String(BACKEND_PORT)], { cwd: dir, env, windowsHide: true });
  backend.stdout?.on("data", (d) => pushLog(String(d)));
  backend.stderr?.on("data", (d) => pushLog(String(d)));
  backend.on("exit", (code) => pushLog(`[main] backend exited with code ${code}`));
  for (let i = 0; i < 120; i++) {
    if (await ping(BACKEND_URL)) return;
    await new Promise((r) => setTimeout(r, 500));
  }
}

function pushLog(line: string) {
  backendLog.push(line.trimEnd());
  if (backendLog.length > 400) backendLog = backendLog.slice(-400);
  mainWindow?.webContents.send("backend-log", line);
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1380,
    height: 900,
    minWidth: 1000,
    minHeight: 700,
    title: "간호기록 음성 녹음 생성기",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  if (DEV_URL) {
    mainWindow.loadURL(DEV_URL);
  } else {
    mainWindow.loadFile(path.join(__dirname, "..", "dist", "index.html"));
  }
  mainWindow.on("closed", () => (mainWindow = null));
}

ipcMain.handle("get-backend-url", () => BACKEND_URL);
ipcMain.handle("get-backend-log", () => backendLog.join("\n"));
ipcMain.handle("get-backend-dir", () => backendDir());
ipcMain.handle("open-path", (_e, p: string) => shell.openPath(p));
ipcMain.handle("show-in-folder", (_e, p: string) => shell.showItemInFolder(p));
ipcMain.handle("choose-directory", async () => {
  const r = await dialog.showOpenDialog({ properties: ["openDirectory", "createDirectory"] });
  return r.canceled ? null : r.filePaths[0];
});
ipcMain.handle("choose-file", async (_e, filters?: { name: string; extensions: string[] }[]) => {
  const r = await dialog.showOpenDialog({ properties: ["openFile"], filters });
  return r.canceled ? null : r.filePaths[0];
});
ipcMain.handle("backend-installed", () => backendInstalled());
ipcMain.handle("setup-backend", async (_e, withF5?: boolean) => {
  const r = await setupBackend(!!withF5);
  pushLog(`[setup] ${r.message}`);
  return r;
});
ipcMain.handle("cancel-setup", () => {
  setupCancelled = true;
  setupChild?.kill();
  return true;
});
ipcMain.handle("check-environment", () => checkEnvironment());
ipcMain.handle("open-external", (_e, url: string) => shell.openExternal(url));
ipcMain.handle("app-version", () => app.getVersion());
ipcMain.handle("restart-backend", async () => {
  backend?.kill();
  backend = null;
  await startBackend();
  return ping(BACKEND_URL);
});

app.whenReady().then(async () => {
  createWindow();
  await startBackend();
  mainWindow?.webContents.send("backend-ready", await ping(BACKEND_URL));
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  backend?.kill();
});
