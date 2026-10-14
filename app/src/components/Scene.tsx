/* Three.js ambient background: a breathing "sound field" of particles plus a
   slow wireframe wave, tinted by the app accent.  Kept deliberately light so
   it never competes with the form UI (no post-processing, ~6k points). */
import { useEffect, useRef } from "react";
import * as THREE from "three";

interface Props {
  /** 0..1 activity level (e.g. playback amplitude) that pumps the field */
  energy?: number;
}

export default function Scene({ energy = 0 }: Props) {
  const ref = useRef<HTMLDivElement | null>(null);
  const energyRef = useRef(energy);
  energyRef.current = energy;

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const prefersReduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "low-power" });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    renderer.setSize(el.clientWidth, el.clientHeight);
    el.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x070b16, 0.055);
    const camera = new THREE.PerspectiveCamera(55, el.clientWidth / el.clientHeight, 0.1, 100);
    camera.position.set(0, 4.5, 12);
    camera.lookAt(0, 0, 0);

    // --- particle field -------------------------------------------------
    const COLS = 110;
    const ROWS = 56;
    const count = COLS * ROWS;
    const positions = new Float32Array(count * 3);
    const base = new Float32Array(count * 2);
    const colors = new Float32Array(count * 3);
    const c1 = new THREE.Color(0x3b82f6);
    const c2 = new THREE.Color(0x22d3ee);
    const c3 = new THREE.Color(0xa78bfa);
    let i = 0;
    for (let r = 0; r < ROWS; r++) {
      for (let c = 0; c < COLS; c++) {
        const x = (c / (COLS - 1) - 0.5) * 34;
        const z = (r / (ROWS - 1) - 0.5) * 18;
        positions[i * 3] = x;
        positions[i * 3 + 1] = 0;
        positions[i * 3 + 2] = z;
        base[i * 2] = x;
        base[i * 2 + 1] = z;
        const t = c / (COLS - 1);
        const col = t < 0.5 ? c1.clone().lerp(c2, t * 2) : c2.clone().lerp(c3, (t - 0.5) * 2);
        colors[i * 3] = col.r;
        colors[i * 3 + 1] = col.g;
        colors[i * 3 + 2] = col.b;
        i++;
      }
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    const mat = new THREE.PointsMaterial({ size: 0.055, vertexColors: true, transparent: true, opacity: 0.85, depthWrite: false });
    const points = new THREE.Points(geo, mat);
    points.position.y = -1.2;
    scene.add(points);

    // --- wireframe ribbon ------------------------------------------------
    const ribbonGeo = new THREE.PlaneGeometry(34, 18, 60, 30);
    const ribbonMat = new THREE.MeshBasicMaterial({ color: 0x1e3a8a, wireframe: true, transparent: true, opacity: 0.16 });
    const ribbon = new THREE.Mesh(ribbonGeo, ribbonMat);
    ribbon.rotation.x = -Math.PI / 2;
    ribbon.position.y = -1.6;
    scene.add(ribbon);
    const ribbonPos = ribbonGeo.attributes.position as THREE.BufferAttribute;
    const ribbonBase = new Float32Array(ribbonPos.array);

    // --- halo rings ------------------------------------------------------
    const rings: THREE.Mesh[] = [];
    for (let k = 0; k < 3; k++) {
      const rg = new THREE.RingGeometry(2.2 + k * 0.9, 2.26 + k * 0.9, 96);
      const rm = new THREE.MeshBasicMaterial({ color: k === 1 ? 0x22d3ee : 0x60a5fa, transparent: true, opacity: 0.18 - k * 0.04, side: THREE.DoubleSide });
      const ring = new THREE.Mesh(rg, rm);
      ring.rotation.x = -Math.PI / 2 + 0.25;
      ring.position.set(6.5, 0.4, -3);
      scene.add(ring);
      rings.push(ring);
    }

    let mouseX = 0;
    let mouseY = 0;
    const onMove = (e: MouseEvent) => {
      mouseX = (e.clientX / window.innerWidth - 0.5) * 2;
      mouseY = (e.clientY / window.innerHeight - 0.5) * 2;
    };
    window.addEventListener("mousemove", onMove);

    const onResize = () => {
      if (!el) return;
      renderer.setSize(el.clientWidth, el.clientHeight);
      camera.aspect = el.clientWidth / el.clientHeight;
      camera.updateProjectionMatrix();
    };
    window.addEventListener("resize", onResize);

    let raf = 0;
    let smoothE = 0;
    const clock = new THREE.Clock();
    const render = () => {
      const t = clock.getElapsedTime();
      smoothE += (energyRef.current - smoothE) * 0.08;
      const amp = 0.35 + smoothE * 1.6;
      const pos = geo.attributes.position as THREE.BufferAttribute;
      for (let p = 0; p < count; p++) {
        const x = base[p * 2];
        const z = base[p * 2 + 1];
        const d = Math.sqrt(x * x + z * z);
        const y = Math.sin(d * 0.55 - t * 1.4) * amp * 0.5 + Math.sin(x * 0.35 + t * 0.6) * 0.25 + Math.cos(z * 0.5 - t * 0.8) * 0.2;
        pos.array[p * 3 + 1] = y;
      }
      pos.needsUpdate = true;
      for (let v = 0; v < ribbonPos.count; v++) {
        const x = ribbonBase[v * 3];
        const yv = ribbonBase[v * 3 + 1];
        ribbonPos.array[v * 3 + 2] = Math.sin(x * 0.3 + t * 0.7) * 0.5 + Math.cos(yv * 0.4 - t * 0.5) * 0.4 * (1 + smoothE);
      }
      ribbonPos.needsUpdate = true;
      rings.forEach((r, k) => {
        r.rotation.z = t * (0.15 + k * 0.07) * (k % 2 ? -1 : 1);
        const s = 1 + Math.sin(t * 1.2 + k) * 0.03 + smoothE * 0.15;
        r.scale.set(s, s, s);
      });
      camera.position.x += (mouseX * 1.2 - camera.position.x) * 0.03;
      camera.position.y += (4.5 - mouseY * 0.8 - camera.position.y) * 0.03;
      camera.lookAt(0, -0.5, 0);
      renderer.render(scene, camera);
      if (!prefersReduced) raf = requestAnimationFrame(render);
    };
    render();

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("resize", onResize);
      geo.dispose();
      mat.dispose();
      ribbonGeo.dispose();
      ribbonMat.dispose();
      rings.forEach((r) => {
        r.geometry.dispose();
        (r.material as THREE.Material).dispose();
      });
      renderer.dispose();
      el.removeChild(renderer.domElement);
    };
  }, []);

  return <div ref={ref} className="scene" aria-hidden="true" />;
}
