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
  setupBackend: (withF5?: boolean): Promise<{ ok: boolean; message: string }> => ipcRenderer.invoke("setup-backend", withF5),
  appVersion: (): Promise<string> => ipcRenderer.invoke("app-version"),
  onBackendReady: (cb: (ok: boolean) => void) => {
    ipcRenderer.on("backend-ready", (_e, ok) => cb(ok));
  },
  onBackendLog: (cb: (line: string) => void) => {
    ipcRenderer.on("backend-log", (_e, line) => cb(line));
  },
});
