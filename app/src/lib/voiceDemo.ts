import { apiUrl } from "./api";

let player: HTMLAudioElement | null = null;

/** Play the synthesised demo sentence for a voice (server caches it per voice). Never the source recordings. */
export async function playVoiceDemo(voiceId: string, setBusy: (id: string) => void, setError: (msg: string) => void): Promise<void> {
  setError("");
  setBusy(voiceId);
  try {
    const r = await fetch(apiUrl(`/api/voices/${voiceId}/demo`));
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
