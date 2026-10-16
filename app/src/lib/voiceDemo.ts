import { apiUrl } from "./api";

export interface DemoOptions { pitch?: number; tempo?: number }

let player: HTMLAudioElement | null = null;

/** Play the demo sentence for a voice (bundled or cached on the server, synthesised once otherwise).
 *  Never the source recordings. ``pitch`` in semitones, ``tempo`` as a rate (1 = as recorded). */
export async function playVoiceDemo(voiceId: string, setBusy: (id: string) => void, setError: (msg: string) => void,
                                    opts: DemoOptions = {}): Promise<void> {
  setError("");
  setBusy(voiceId);
  try {
    const q = new URLSearchParams();
    if (opts.pitch) q.set("pitch", String(opts.pitch));
    if (opts.tempo && opts.tempo !== 1) q.set("tempo", String(opts.tempo));
    const r = await fetch(apiUrl(`/api/voices/${voiceId}/demo${q.toString() ? "?" + q.toString() : ""}`));
    if (!r.ok) {
      let msg = `샘플 합성 실패 (${r.status})`;
      try { msg = (await r.json()).detail || msg; } catch { /* ignore */ }
      throw new Error(msg);
    }
    const url = URL.createObjectURL(await r.blob());
    player?.pause();
    player = new Audio(url);
    player.onended = () => URL.revokeObjectURL(url);
    await player.play();
  } catch (e) {
    setError(e instanceof Error ? e.message : String(e));
  } finally {
    setBusy("");
  }
}
