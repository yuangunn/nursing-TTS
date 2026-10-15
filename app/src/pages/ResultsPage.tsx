import { useEffect, useMemo, useState } from "react";
import Visualizer from "../components/Visualizer";
import { apiUrl, del, ExportReport, get, post, RecordingItem, Settings } from "../lib/api";
import { useEnergy } from "../lib/energy";

type Filter = "all" | "pending" | "approved" | "rejected" | "failed";

export default function ResultsPage() {
  const [items, setItems] = useState<RecordingItem[]>([]);
  const [folder, setFolder] = useState("");
  const [sel, setSel] = useState<RecordingItem | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  const [asrOk, setAsrOk] = useState(false);
  const [exp, setExp] = useState({ name: "", sample_rate: 16000, include_fillers: false, only_approved: false, exclude_rejected: true, exclude_failed_verify: true, train: 90, val: 5, test: 5, formats: ["ljspeech", "nemo", "whisper", "csv"], max_clip_sec: 30 });
  const [report, setReport] = useState<ExportReport | null>(null);
  const setEnergy = useEnergy();

  const load = async () => {
    try {
      const r = await get<{ folder: string; items: RecordingItem[] }>("/api/recordings");
      setItems(r.items.filter((i) => !i.rel.startsWith("_exports/")));
      setFolder(r.folder);
      const e = await get<{ asr: { available: boolean } }>("/api/engines");
      setAsrOk(e.asr.available);
      setErr("");
    } catch (e) {
      setErr(String(e));
    }
  };
  useEffect(() => {
    load();
    get<Settings>("/api/settings").then((s) => setExp((x) => ({ ...x, sample_rate: s.sample_rate === 24000 ? 16000 : s.sample_rate }))).catch(() => undefined);
  }, []);

  const [sortCer, setSortCer] = useState(false);
  const REASONS = ["발음 오류", "잡음 과다", "끊김·반복", "대본 오류", "목소리 다름", "기타"];
  const shown = useMemo(() => {
    const arr = items.filter((i) => {
      if (filter === "failed") return i.verify?.passed === false;
      if (filter !== "all" && (i.review || "pending") !== filter) return false;
      if (q && !`${i.name} ${i.patient} ${i.record_kind} ${i.voice_name}`.includes(q)) return false;
      return true;
    });
    // worst CER first so review time goes where the problems are
    return sortCer ? [...arr].sort((a, b) => (b.verify?.cer_best ?? -1) - (a.verify?.cer_best ?? -1)) : arr;
  }, [items, filter, q, sortCer]);

  const stats = {
    total: items.length,
    approved: items.filter((i) => i.review === "approved").length,
    rejected: items.filter((i) => i.review === "rejected").length,
    failed: items.filter((i) => i.verify?.passed === false).length,
    minutes: items.reduce((a, i) => a + (i.duration || 0), 0) / 60,
  };

  const review = async (it: RecordingItem, status: string, note = "") => {
    await post("/api/recordings/review", { rel: it.rel, status, note });
    setItems((arr) => arr.map((x) => (x.rel === it.rel ? { ...x, review: status, review_note: note } : x)));
    if (sel?.rel === it.rel) setSel({ ...it, review: status, review_note: note });
  };
  // Same script (text_override), same voice and noise setup, new seed.
  const regenerate = async (it: RecordingItem) => {
    setBusy("같은 대본으로 다시 합성 중… (1~3분)");
    setErr("");
    try {
      const m = await get<{ template: string; patient: object; datetime: string; style: string; voice_id: string; spoken_text: string;
        noise?: { enabled?: boolean; level?: number; types?: string[] }; disfluency_level?: number }>(`/api/output/meta?rel=${encodeURIComponent(it.rel)}`);
      const job = await post<{ id: string }>("/api/generate", {
        template: m.template, patient: m.patient, datetime: m.datetime, style: m.style, voice_id: m.voice_id,
        noise: { enabled: !!m.noise?.enabled, level: m.noise?.level ?? 35, types: m.noise?.types ?? [] },
        disfluency: m.disfluency_level ?? 0, text_override: m.spoken_text,
      });
      for (;;) {
        await new Promise((r) => setTimeout(r, 3000));
        const j = await get<{ status: string; error?: string }>(`/api/jobs/${job.id}`);
        if (j.status === "done") break;
        if (j.status === "error" || j.status === "cancelled") throw new Error(j.error || "다시 합성 실패");
      }
      await load();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy("");
    }
  };
  const remove = async (it: RecordingItem) => {
    if (!confirm(`${it.name} 과 .txt/.json 을 삭제할까요?`)) return;
    await del(`/api/recordings?rel=${encodeURIComponent(it.rel)}`);
    setItems((arr) => arr.filter((x) => x.rel !== it.rel));
    if (sel?.rel === it.rel) setSel(null);
  };
  const verifyOne = async (it: RecordingItem) => {
    setBusy("ASR 검증 중… (첫 실행 시 모델 로딩)");
    try {
      const v = await post<RecordingItem["verify"]>("/api/recordings/verify", { rel: it.rel });
      setItems((arr) => arr.map((x) => (x.rel === it.rel ? { ...x, verify: v } : x)));
      if (sel?.rel === it.rel) setSel({ ...it, verify: v });
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy("");
    }
  };
  const doExport = async () => {
    setBusy("내보내는 중…");
    setReport(null);
    try {
      const total = exp.train + exp.val + exp.test || 100;
      const r = await post<ExportReport>("/api/dataset/export", {
        name: exp.name, formats: exp.formats, sample_rate: exp.sample_rate, include_fillers: exp.include_fillers,
        only_approved: exp.only_approved, exclude_rejected: exp.exclude_rejected, exclude_failed_verify: exp.exclude_failed_verify,
        split: { train: exp.train / total, val: exp.val / total, test: exp.test / total },
        max_clip_sec: exp.max_clip_sec,
      });
      setReport(r);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy("");
    }
  };
  const next = (dir: 1 | -1) => {
    if (!sel) return;
    const idx = shown.findIndex((x) => x.rel === sel.rel);
    const n = shown[idx + dir];
    if (n) setSel(n);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!sel) return;
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (e.key === "a" || e.key === "A") review(sel, "approved");
      else if (e.key === "r" || e.key === "R") review(sel, "rejected");
      else if (e.key === "ArrowDown" || e.key === "ArrowRight") { e.preventDefault(); next(1); }
      else if (e.key === "ArrowUp" || e.key === "ArrowLeft") { e.preventDefault(); next(-1); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sel, shown]);

  const badge = (it: RecordingItem) => {
    if (it.review === "approved") return <span className="badge ok">승인</span>;
    if (it.review === "rejected") return <span className="badge bad">반려</span>;
    if (it.verify?.passed === false) return <span className="badge warn">ASR 불일치</span>;
    return <span className="badge">대기</span>;
  };

  return (
    <div className="cols" style={{ gridTemplateColumns: "minmax(460px, 1.1fr) minmax(420px, 1fr)" }}>
      <div>
        <div className="panel">
          <h2>결과물 · QA 리뷰 <span className="hint">{folder}</span>
            <span style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
              <button className="small" onClick={load}>새로고침</button>
              <button className="small" onClick={() => window.nursing?.openPath(folder)}>📂 폴더</button>
            </span>
          </h2>
          <div className="stat">
            <div><div className="k">녹음</div><div className="v">{stats.total}</div></div>
            <div><div className="k">총 분량</div><div className="v">{stats.minutes.toFixed(1)}분</div></div>
            <div><div className="k">승인</div><div className="v">{stats.approved}</div></div>
            <div><div className="k">반려</div><div className="v">{stats.rejected}</div></div>
            <div><div className="k">ASR 불일치</div><div className="v">{stats.failed}</div></div>
          </div>
          <div className="row">
            <div className="narrow">
              <div className="tabs" style={{ padding: 3 }}>
                {(["all", "pending", "approved", "rejected", "failed"] as Filter[]).map((f) => (
                  <button key={f} className={filter === f ? "active" : ""} style={{ padding: "4px 10px", fontSize: 12 }} onClick={() => setFilter(f)}>
                    {{ all: "전체", pending: "대기", approved: "승인", rejected: "반려", failed: "ASR 불일치" }[f]}
                  </button>
                ))}
              </div>
            </div>
            <div><input type="text" placeholder="환자명 / 파일명 / 기록종류 / 목소리 검색" value={q} onChange={(e) => setQ(e.target.value)} /></div>
            <div className="narrow"><button className={"small" + (sortCer ? " active" : "")} onClick={() => setSortCer(!sortCer)} title="ASR 검증 CER이 높은 녹음부터 보여 줍니다">{sortCer ? "CER 높은 순 ✓" : "CER 높은 순"}</button></div>
          </div>
          <div style={{ maxHeight: 420, overflow: "auto" }}>
            <table className="items">
              <thead><tr><th>파일</th><th>종류</th><th>목소리</th><th>길이</th><th>CER</th><th>상태</th></tr></thead>
              <tbody>
                {shown.map((it) => (
                  <tr key={it.rel} onClick={() => setSel(it)} style={{ cursor: "pointer", background: sel?.rel === it.rel ? "rgba(56,189,248,0.12)" : undefined }}>
                    <td title={it.rel}>{it.name}</td>
                    <td>{it.record_kind || "-"}</td>
                    <td>{it.voice_name || "-"}</td>
                    <td>{it.duration ? `${it.duration}s` : ""}</td>
                    <td>{it.verify?.cer_best !== undefined ? `${Math.round((it.verify.cer_best || 0) * 100)}%` : "-"}</td>
                    <td>{badge(it)}</td>
                  </tr>
                ))}
                {!shown.length && <tr><td colSpan={6} className="muted">녹음이 없습니다.</td></tr>}
              </tbody>
            </table>
          </div>
          {err && <div className="error">{err}</div>}
        </div>

        <div className="panel">
          <h2>데이터셋 내보내기 <span className="hint">STT 학습용 manifest + 16kHz wav</span></h2>
          <div className="row">
            <div><label>데이터셋 이름</label><input type="text" value={exp.name} placeholder="비우면 dataset_날짜" onChange={(e) => setExp({ ...exp, name: e.target.value })} /></div>
            <div className="narrow"><label>샘플레이트</label>
              <select value={exp.sample_rate} onChange={(e) => setExp({ ...exp, sample_rate: Number(e.target.value) })}>
                <option value={16000}>16000 (Whisper/NeMo)</option><option value={22050}>22050</option><option value={24000}>24000</option>
              </select>
            </div>
          </div>
          <div className="row">
            <div className="narrow"><label>train %</label><input type="number" value={exp.train} onChange={(e) => setExp({ ...exp, train: Number(e.target.value) })} style={{ width: 70 }} /></div>
            <div className="narrow"><label>val %</label><input type="number" value={exp.val} onChange={(e) => setExp({ ...exp, val: Number(e.target.value) })} style={{ width: 70 }} /></div>
            <div className="narrow"><label>test %</label><input type="number" value={exp.test} onChange={(e) => setExp({ ...exp, test: Number(e.target.value) })} style={{ width: 70 }} /></div>
            <div className="checks">
              {[["ljspeech", "LJSpeech metadata.csv"], ["nemo", "NeMo manifest.jsonl"], ["whisper", "Whisper 파인튜닝 jsonl"], ["csv", "dataset.csv"]].map(([k, l]) => (
                <label key={k}><input type="checkbox" checked={exp.formats.includes(k)} onChange={() => setExp({ ...exp, formats: exp.formats.includes(k) ? exp.formats.filter((x) => x !== k) : [...exp.formats, k] })} /> {l}</label>
              ))}
            </div>
          </div>
          <div className="checks">
            <label><input type="checkbox" checked={exp.only_approved} onChange={(e) => setExp({ ...exp, only_approved: e.target.checked })} /> 승인된 것만</label>
            <label><input type="checkbox" checked={exp.exclude_rejected} onChange={(e) => setExp({ ...exp, exclude_rejected: e.target.checked })} /> 반려 제외</label>
            <label><input type="checkbox" checked={exp.exclude_failed_verify} onChange={(e) => setExp({ ...exp, exclude_failed_verify: e.target.checked })} /> ASR 불일치 제외</label>
            <label><input type="checkbox" checked={exp.include_fillers} onChange={(e) => setExp({ ...exp, include_fillers: e.target.checked })} /> 전사에 추임새 포함(verbatim)</label>
            <label title="합성 때 기록한 문장 구간으로 자르므로 전사가 정확히 맞습니다. Whisper는 30초 창이라 긴 녹음을 그대로 못 넣습니다"><input type="checkbox" checked={exp.max_clip_sec > 0} onChange={(e) => setExp({ ...exp, max_clip_sec: e.target.checked ? 30 : 0 })} /> 긴 녹음을 30초 이하로 분할 (Whisper 학습용)</label>
          </div>
          <div className="row" style={{ marginTop: 8 }}>
            <div className="narrow"><button className="primary" onClick={doExport} disabled={!!busy}>📦 내보내기</button></div>
            {report && <div className="narrow"><button onClick={() => window.nursing?.openPath(report.folder)}>📂 {report.name} 열기</button></div>}
            <div className="muted">{busy}</div>
          </div>
          {report && (
            <div className="muted" style={{ marginTop: 6 }}>
              {report.total}개 · {(report.total_duration_sec / 60).toFixed(1)}분 · train {report.counts.train} / val {report.counts.val} / test {report.counts.test} · 제외: 반려 {report.skipped.rejected}, 미승인 {report.skipped.not_approved}, ASR {report.skipped.failed_verify} · 파일: {report.files.join(", ")}
            </div>
          )}
        </div>
      </div>

      <div>
        {sel ? (
          <div className="panel highlight">
            <h2>{sel.name}
              <span style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
                <button className="small" onClick={() => next(-1)}>◀</button>
                <button className="small" onClick={() => next(1)}>▶</button>
              </span>
            </h2>
            <Visualizer autoPlay src={apiUrl(`/api/output/file?rel=${encodeURIComponent(sel.rel)}`)} onEnergy={setEnergy} height={130} />
            <div className="muted" style={{ margin: "8px 0" }}>
              {sel.record_kind} · {sel.voice_name || "목소리 없음"} · {sel.engine} · {sel.duration}s · 소음 {sel.noise ? "O" : "X"} · 장비 {sel.channel || "-"} · 흐트러짐 {sel.disfluency ?? 0} · 시그널 {sel.signal_format || "-"}
            </div>
            <div className="preview" style={{ minHeight: 120 }}>
              <span className="signal">{(sel.spoken_text || "").split("\n")[0]}</span>{"\n" + (sel.spoken_text || "").split("\n").slice(1).join("\n")}
            </div>
            {sel.verbatim_text && sel.verbatim_text !== sel.spoken_text && (
              <details style={{ marginTop: 6 }}><summary className="muted">추임새 포함 발화(verbatim) 보기</summary><div className="preview" style={{ minHeight: 60 }}>{sel.verbatim_text}</div></details>
            )}
            {sel.verify && (
              <div className="muted" style={{ marginTop: 6 }}>
                ASR 검증: {sel.verify.error ? <span className="badge bad">{sel.verify.error}</span> : <>CER {Math.round((sel.verify.cer_best || 0) * 100)}% (기준 {Math.round((sel.verify.threshold || 0) * 100)}%) {sel.verify.passed ? <span className="badge ok">통과</span> : <span className="badge bad">불일치</span>}<div style={{ marginTop: 4 }}>인식 결과: {sel.verify.hyp}</div></>}
              </div>
            )}
            {sel.chunk_verify && (
              <div className="muted" style={{ marginTop: 4 }}>
                문장 검증: {sel.chunk_verify.checked}문장 중 재합성 {sel.chunk_verify.retried}, 기준 초과 {sel.chunk_verify.still_bad}
                {sel.chunk_verify.max_cer !== null && <> · 최고 CER {Math.round(sel.chunk_verify.max_cer * 100)}%</>}
                {sel.chunk_verify.still_bad > 0 && <span className="badge warn" style={{ marginLeft: 6 }}>확인 필요</span>}
              </div>
            )}
            <div className="row" style={{ marginTop: 10 }}>
              <div className="narrow"><button className="primary" onClick={() => review(sel, "approved")}>✓ 승인 (A)</button></div>
              <div className="narrow"><button className="danger" onClick={() => review(sel, "rejected")}>✗ 반려 (R)</button></div>
              <div className="narrow"><button onClick={() => review(sel, "pending")}>대기로</button></div>
              {sel.review === "rejected" && (
                <div className="narrow">
                  <select value={sel.review_note || ""} onChange={(e) => review(sel, "rejected", e.target.value)} title="반려 사유 (json에 저장)">
                    <option value="">반려 사유…</option>
                    {REASONS.map((r) => <option key={r} value={r}>{r}</option>)}
                  </select>
                </div>
              )}
              <div className="narrow"><button onClick={() => regenerate(sel)} disabled={!!busy} title="같은 대본·목소리·소음 설정으로 새 시드로 다시 합성합니다 (원본은 그대로)">🔁 다시 합성</button></div>
              <div className="narrow"><button onClick={() => verifyOne(sel)} disabled={!asrOk || !!busy} title={asrOk ? "" : "설정에서 faster-whisper 설치 필요"}>🔎 ASR 검증</button></div>
              <div className="narrow"><button onClick={() => window.nursing?.showInFolder(`${folder}/${sel.rel}`)}>폴더</button></div>
              <div className="narrow"><button className="danger small" onClick={() => remove(sel)}>삭제</button></div>
            </div>
            {busy && <div className="muted">{busy}</div>}
          </div>
        ) : (
          <div className="panel muted">왼쪽 목록에서 녹음을 선택하면 재생·검토할 수 있습니다. 승인/반려 상태는 각 녹음의 .json에 저장되고 내보내기 시 필터로 쓰입니다.</div>
        )}
      </div>
    </div>
  );
}
