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

function findPython(dir: string): string | null {
  const candidates =
    process.platform === "win32"
      ? [path.join(dir, ".venv", "Scripts", "python.exe"), "python", "py"]
      : [path.join(dir, ".venv", "bin", "python"), "python3", "python"];
  for (const c of candidates) {
    if (c.includes(path.sep)) {
      if (fs.existsSync(c)) return c;
    } else {
      return c; // rely on PATH
    }
  }
  return null;
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
    backendLog.push("[main] python not found");
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
