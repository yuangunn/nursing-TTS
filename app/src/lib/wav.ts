/* Browser-side helpers: record from the microphone and encode 16-bit PCM WAV. */

export function encodeWav(samples: Float32Array, sampleRate: number): Blob {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const writeString = (off: number, s: string) => {
    for (let i = 0; i < s.length; i++) view.setUint8(off + i, s.charCodeAt(i));
  };
  writeString(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeString(8, "WAVE");
  writeString(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(36, "data");
  view.setUint32(40, samples.length * 2, true);
  let off = 44;
  for (let i = 0; i < samples.length; i++, off += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([buffer], { type: "audio/wav" });
}

export async function blobToWav(blob: Blob): Promise<Blob> {
  const ctx = new AudioContext();
  try {
    const buf = await ctx.decodeAudioData(await blob.arrayBuffer());
    const ch = buf.numberOfChannels;
    const mono = new Float32Array(buf.length);
    for (let c = 0; c < ch; c++) {
      const data = buf.getChannelData(c);
      for (let i = 0; i < buf.length; i++) mono[i] += data[i] / ch;
    }
    return encodeWav(mono, buf.sampleRate);
  } finally {
    await ctx.close();
  }
}

export interface Recorder {
  stop(): Promise<Blob>;
  level(): number;
}

export async function startRecording(onLevel?: (v: number) => void): Promise<Recorder> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false, channelCount: 1 },
  });
  const ctx = new AudioContext();
  const src = ctx.createMediaStreamSource(stream);
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 1024;
  src.connect(analyser);
  const chunks: Blob[] = [];
  const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "";
  const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
  rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  rec.start(250);
  const buf = new Float32Array(analyser.fftSize);
  let current = 0;
  let raf = 0;
  const tick = () => {
    analyser.getFloatTimeDomainData(buf);
    let sum = 0;
    for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
    current = Math.sqrt(sum / buf.length);
    onLevel?.(current);
    raf = requestAnimationFrame(tick);
  };
  tick();
  return {
    level: () => current,
    stop: () =>
      new Promise<Blob>((resolve) => {
        rec.onstop = async () => {
          cancelAnimationFrame(raf);
          stream.getTracks().forEach((t) => t.stop());
          await ctx.close();
          const webm = new Blob(chunks, { type: rec.mimeType || "audio/webm" });
          resolve(await blobToWav(webm));
        };
        rec.stop();
      }),
  };
}
