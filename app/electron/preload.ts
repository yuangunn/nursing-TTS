import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("nursing", {
  getBackendUrl: (): Promise<string> => ipcRenderer.invoke("get-backend-url"),
  getBackendLog: (): Promise<string> => ipcRenderer.invoke("get-backend-log"),
  getBackendDir: (): Promise<string> => ipcRenderer.invoke("get-backend-dir"),
  openPath: (p: string): Promise<string> => ipcRenderer.invoke("open-path", p),
  showInFolder: (p: string): Promise<void> => ipcRenderer.invoke("show-in-folder", p),
  chooseDirectory: (): Promise<string | null> => ipcRenderer.invoke("choose-directory"),
  chooseFile: (filters?: { name: string; extensions: string[] }[]): Promise<string | null> =>
    ipcRenderer.invoke("choose-file", filters),
  restartBackend: (): Promise<boolean> => ipcRenderer.invoke("restart-backend"),
  backendInstalled: (): Promise<boolean> => ipcRenderer.invoke("backend-installed"),
  setupBackend: (withQwen?: boolean): Promise<{ ok: boolean; message: string }> => ipcRenderer.invoke("setup-backend", withQwen),
  appVersion: (): Promise<string> => ipcRenderer.invoke("app-version"),
  cancelSetup: (): Promise<boolean> => ipcRenderer.invoke("cancel-setup"),
  checkEnvironment: (): Promise<unknown> => ipcRenderer.invoke("check-environment"),
  openExternal: (url: string): Promise<void> => ipcRenderer.invoke("open-external", url),
  checkUpdate: (force?: boolean): Promise<unknown> => ipcRenderer.invoke("check-update", force),
  getUpdateSettings: (): Promise<unknown> => ipcRenderer.invoke("get-update-settings"),
  setUpdateSettings: (patch: unknown): Promise<unknown> => ipcRenderer.invoke("set-update-settings", patch),
  onUpdateAvailable: (cb: (info: unknown) => void) => {
    const handler = (_e: unknown, info: unknown) => cb(info);
    ipcRenderer.on("update-available", handler);
    return () => ipcRenderer.removeListener("update-available", handler);
  },
  onSetupProgress: (cb: (p: unknown) => void) => {
    const handler = (_e: unknown, p: unknown) => cb(p);
    ipcRenderer.on("setup-progress", handler);
    return () => ipcRenderer.removeListener("setup-progress", handler);
  },
  onBackendReady: (cb: (ok: boolean) => void) => {
    ipcRenderer.on("backend-ready", (_e, ok) => cb(ok));
  },
  onBackendLog: (cb: (line: string) => void) => {
    ipcRenderer.on("backend-log", (_e, line) => cb(line));
  },
});
