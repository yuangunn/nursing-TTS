import { app, BrowserWindow, dialog, ipcMain, shell } from "electron";
import { ChildProcess, spawn } from "child_process";
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

/** Create the venv in userData and install the backend requirements (streams log lines to the renderer). */
async function setupBackend(withF5 = false): Promise<{ ok: boolean; message: string }> {
  const dir = backendDir();
  const venv = venvDir();
  const run = (cmd: string, args: string[], cwd: string) =>
    new Promise<number>((resolve) => {
      pushLog(`[setup] $ ${cmd} ${args.join(" ")}`);
      const child = spawn(cmd, args, { cwd, env: { ...process.env, PYTHONUTF8: "1", PIP_DISABLE_PIP_VERSION_CHECK: "1" }, windowsHide: true, shell: process.platform === "win32" });
      child.stdout?.on("data", (d) => pushLog(String(d)));
      child.stderr?.on("data", (d) => pushLog(String(d)));
      child.on("error", (e) => { pushLog(`[setup] ${e.message}`); resolve(-1); });
      child.on("exit", (code) => resolve(code ?? -1));
    });
  if (!fs.existsSync(venvPython(venv))) {
    let created = false;
    for (const py of systemPythonCandidates()) {
      const args = py === "py" ? ["-3", "-m", "venv", venv] : ["-m", "venv", venv];
      if ((await run(py, args, dir)) === 0 && fs.existsSync(venvPython(venv))) { created = true; break; }
    }
    if (!created) return { ok: false, message: "Python 3.10 이상을 찾지 못했습니다. python.org 또는 Homebrew(brew install python)로 설치한 뒤 다시 시도하세요." };
  }
  const py = venvPython(venv);
  if ((await run(py, ["-m", "pip", "install", "--upgrade", "pip"], dir)) !== 0) return { ok: false, message: "pip 업그레이드 실패 (로그 확인)" };
  if ((await run(py, ["-m", "pip", "install", "-r", path.join(dir, "requirements.txt")], dir)) !== 0) return { ok: false, message: "백엔드 의존성 설치 실패 (로그 확인)" };
  if (withF5 && (await run(py, ["-m", "pip", "install", "-r", path.join(dir, "requirements-f5.txt")], dir)) !== 0) return { ok: false, message: "F5-TTS 설치 실패 (로그 확인)" };
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
  if (r.ok) {
    backend?.kill();
    backend = null;
    await startBackend();
  }
  return r;
});
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
