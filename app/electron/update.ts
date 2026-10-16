import * as fs from "fs";
import * as path from "path";

/** Startup update check against GitHub releases (user request, 2026-10-16): tell the user when a newer
 *  version exists, with "skip this version". The repo is private, so a token can be stored for the check. */

export const DEFAULT_FEED = "https://api.github.com/repos/yuangunn/nursing-TTS/releases?per_page=20";

export interface UpdateSettings { skipVersion: string; token: string; feedUrl: string; lastCheck: number; lastResult?: UpdateInfo }
export interface UpdateInfo {
  current: string; latest: string; url: string; notes: string; published: string;
  newer: boolean; skipped: boolean; error?: string; checkedAt: number;
}

export function parseVersion(v: string): { nums: number[]; pre: string } | null {
  const m = /^v?(\d+)\.(\d+)\.(\d+)(?:-([\w.]+))?/.exec((v || "").trim());
  return m ? { nums: [Number(m[1]), Number(m[2]), Number(m[3])], pre: m[4] || "" } : null;
}

/** true when ``a`` is a newer release than ``b`` (0.1.3 > 0.1.2-beta, 0.1.2 > 0.1.2-beta, 0.1.2-beta == 0.1.2-beta). */
export function isNewer(a: string, b: string): boolean {
  const x = parseVersion(a), y = parseVersion(b);
  if (!x || !y) return false;
  for (let i = 0; i < 3; i++) if (x.nums[i] !== y.nums[i]) return x.nums[i] > y.nums[i];
  if (!x.pre && y.pre) return true;      // final release beats its own beta
  if (x.pre && !y.pre) return false;
  return x.pre > y.pre;
}

export function loadSettings(userData: string): UpdateSettings {
  try {
    const raw = JSON.parse(fs.readFileSync(path.join(userData, "update.json"), "utf-8"));
    return { skipVersion: "", token: "", feedUrl: DEFAULT_FEED, lastCheck: 0, ...raw };
  } catch {
    return { skipVersion: "", token: "", feedUrl: DEFAULT_FEED, lastCheck: 0 };
  }
}

export function saveSettings(userData: string, s: UpdateSettings): void {
  fs.mkdirSync(userData, { recursive: true });
  fs.writeFileSync(path.join(userData, "update.json"), JSON.stringify(s, null, 2), "utf-8");
}

interface Release { tag_name: string; html_url: string; body?: string; published_at?: string; draft?: boolean; prerelease?: boolean }

/** Fetch the release list and compare the highest version with ``current``. */
export async function checkForUpdate(current: string, s: UpdateSettings): Promise<UpdateInfo> {
  const base: UpdateInfo = { current, latest: "", url: "", notes: "", published: "", newer: false, skipped: false, checkedAt: Date.now() };
  try {
    const headers: Record<string, string> = { Accept: "application/vnd.github+json", "User-Agent": "nursing-tts-app" };
    if (s.token) headers.Authorization = `Bearer ${s.token}`;
    const r = await fetch(s.feedUrl || DEFAULT_FEED, { headers, signal: AbortSignal.timeout(8000) });
    if (!r.ok) {
      return { ...base, error: r.status === 404 || r.status === 401 ? "릴리스를 읽을 수 없습니다 (비공개 저장소: 설정에서 GitHub 토큰을 등록하세요)" : `확인 실패 (${r.status})` };
    }
    const releases = (await r.json()) as Release[];
    let best: Release | null = null;
    for (const rel of releases) {
      if (rel.draft || !parseVersion(rel.tag_name)) continue;
      if (!best || isNewer(rel.tag_name, best.tag_name)) best = rel;
    }
    if (!best) return { ...base, error: "릴리스가 없습니다" };
    const latest = best.tag_name.replace(/^v/, "");
    return { ...base, latest, url: best.html_url, notes: (best.body || "").slice(0, 2000), published: best.published_at || "",
             newer: isNewer(latest, current), skipped: !!s.skipVersion && s.skipVersion === latest };
  } catch (e) {
    return { ...base, error: `확인 실패: ${e instanceof Error ? e.message : String(e)}` };
  }
}
