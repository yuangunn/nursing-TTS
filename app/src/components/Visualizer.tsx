/* Audio-reactive visualizer: a Three.js ring of bars driven by an AnalyserNode
   attached to an <audio> element.  Reports a smoothed energy value upward so
   the background Scene can breathe with playback. */
import { MutableRefObject, useEffect, useRef } from "react";
import * as THREE from "three";

interface Props {
  src: string;
  autoPlay?: boolean;
  onEnergy?: (e: number) => void;
  height?: number;
  onTime?: (t: number) => void;                                   // playback position, every animation frame while playing
  seekRef?: MutableRefObject<((t: number) => void) | null>;       // parent calls seekRef.current(seconds) to jump (and play)
}

const BARS = 96;

export default function Visualizer({ src, autoPlay = false, onEnergy, height = 150, onTime, seekRef }: Props) {
  const wrap = useRef<HTMLDivElement | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const energyCb = useRef(onEnergy);
  energyCb.current = onEnergy;
  const timeCb = useRef(onTime);
  timeCb.current = onTime;
  useEffect(() => {
    if (!seekRef) return;
    seekRef.current = (t: number) => {
      const a = audioRef.current;
      if (!a) return;
      a.currentTime = Math.max(0, t);
      a.play().catch(() => undefined);
      timeCb.current?.(a.currentTime);
    };
    return () => { seekRef.current = null; };
  }, [seekRef, src]);

  useEffect(() => {
    const el = wrap.current;
    const audio = audioRef.current;
    if (!el || !audio) return;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "low-power" });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    renderer.setSize(el.clientWidth, height);
    el.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(40, el.clientWidth / height, 0.1, 50);
    camera.position.set(0, 3.2, 6.5);
    camera.lookAt(0, 0, 0);

    const bars: THREE.Mesh[] = [];
    const geo = new THREE.BoxGeometry(0.09, 1, 0.09);
    for (let i = 0; i < BARS; i++) {
      const hue = 0.55 + (i / BARS) * 0.2;
      const m = new THREE.MeshBasicMaterial({ color: new THREE.Color().setHSL(hue, 0.9, 0.6), transparent: true, opacity: 0.9 });
      const bar = new THREE.Mesh(geo, m);
      const a = (i / BARS) * Math.PI * 2;
      bar.position.set(Math.cos(a) * 2.4, 0, Math.sin(a) * 2.4);
      bar.rotation.y = -a;
      scene.add(bar);
      bars.push(bar);
    }
    const ringGeo = new THREE.RingGeometry(2.1, 2.14, 128);
    const ring = new THREE.Mesh(ringGeo, new THREE.MeshBasicMaterial({ color: 0x22d3ee, transparent: true, opacity: 0.4, side: THREE.DoubleSide }));
    ring.rotation.x = -Math.PI / 2;
    scene.add(ring);

    let ctx: AudioContext | null = null;
    let analyser: AnalyserNode | null = null;
    let data: Uint8Array | null = null;
    const connect = () => {
      if (ctx) return;
      try {
        ctx = new AudioContext();
        const srcNode = ctx.createMediaElementSource(audio);
        analyser = ctx.createAnalyser();
        analyser.fftSize = 256;
        analyser.smoothingTimeConstant = 0.82;
        srcNode.connect(analyser);
        analyser.connect(ctx.destination);
        data = new Uint8Array(analyser.frequencyBinCount);
      } catch {
        ctx = null;
      }
    };
    audio.addEventListener("play", connect);

    let raf = 0;
    const clock = new THREE.Clock();
    const render = () => {
      const t = clock.getElapsedTime();
      let energy = 0;
      if (analyser && data && !audio.paused) {
        analyser.getByteFrequencyData(data as Uint8Array<ArrayBuffer>);
        let sum = 0;
        for (let i = 0; i < BARS; i++) {
          const v = data[Math.min(data.length - 1, Math.floor((i / BARS) * data.length * 0.6))] / 255;
          sum += v;
          const h = 0.08 + v * 2.2;
          bars[i].scale.y += (h - bars[i].scale.y) * 0.35;
          bars[i].position.y = bars[i].scale.y / 2 - 0.5;
        }
        energy = sum / BARS;
      } else {
        for (let i = 0; i < BARS; i++) {
          const h = 0.08 + (Math.sin(t * 1.5 + i * 0.3) + 1) * 0.06;
          bars[i].scale.y += (h - bars[i].scale.y) * 0.1;
          bars[i].position.y = bars[i].scale.y / 2 - 0.5;
        }
      }
      ring.rotation.z = t * 0.2;
      scene.rotation.y = t * 0.12;
      energyCb.current?.(energy);
      if (!audio.paused) timeCb.current?.(audio.currentTime);
      renderer.render(scene, camera);
      raf = requestAnimationFrame(render);
    };
    render();

    const onResize = () => {
      renderer.setSize(el.clientWidth, height);
      camera.aspect = el.clientWidth / height;
      camera.updateProjectionMatrix();
    };
    window.addEventListener("resize", onResize);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
      audio.removeEventListener("play", connect);
      energyCb.current?.(0);
      ctx?.close().catch(() => undefined);
      geo.dispose();
      ringGeo.dispose();
      bars.forEach((b) => (b.material as THREE.Material).dispose());
      renderer.dispose();
      if (renderer.domElement.parentNode === el) el.removeChild(renderer.domElement);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [src, height]);

  return (
    <div className="viz">
      <div ref={wrap} className="viz-canvas" style={{ height }} />
      <audio ref={audioRef} controls autoPlay={autoPlay} src={src} crossOrigin="anonymous"
        onSeeked={(e) => timeCb.current?.((e.target as HTMLAudioElement).currentTime)} onPause={(e) => timeCb.current?.((e.target as HTMLAudioElement).currentTime)} />
    </div>
  );
}
