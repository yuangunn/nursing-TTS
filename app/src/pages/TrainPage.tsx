import { useEffect, useState } from "react";
import { apiUrl, del, get, patch, post, postForm, Voice } from "../lib/api";

interface FtStatus { available: boolean; message: string; active: string | null; min_items: number; defaults: { epochs: number } }
interface DsSummary { id: string; name: string; voice_id: string; created: number; items: number; included: number; confirmed: number; minutes: number }
interface Clip { id: string; text: string; include: boolean; confirmed: boolean; duration: number; source: string }
interface Dataset extends DsSummary { clips: Clip[] }
interface FtModel {
  id: string; name: string; dataset_id: string; created: number; stage: string; message?: string; running: boolean; ready: boolean;
  epoch?: number; epochs: number; step?: number; steps?: number; loss?: number; eta_s?: number; voice?: string; minutes?: number;
  val_loss?: number | null; best_epoch?: number | null;
}

const STAGE: Record<string, string> = {
  queued: "준비 중", load: "모델 불러오는 중", encode: "음성 코드 만드는 중", train: "학습 중", save: "저장 중",
  done: "완료", error: "오류", cancelled: "취소됨",
};
const mmss = (s?: number) => (s == null ? "" : `${Math.floor(s / 60)}분 ${String(Math.round(s % 60)).padStart(2, "0")}초`);

/** 목소리 학습: one speaker's clips -> transcript check -> LoRA training -> a new voice in the list. */
export default function TrainPage() {
  const [st, setSt] = useState<FtStatus | null>(null);
  const [voices, setVoices] = useState<Voice[]>([]);
  const [sets, setSets] = useState<DsSummary[]>([]);
  const [models, setModels] = useState<FtModel[]>([]);
  const [ds, setDs] = useState<Dataset | null>(null);
  const [srcVoice, setSrcVoice] = useState("");
  const [recName, setRecName] = useState("");
  const [recVoice, setRecVoice] = useState("");
  const [files, setFiles] = useState<FileList | null>(null);
  const [transcribe, setTranscribe] = useState(true);
  const [name, setName] = useState("");
  const [epochs, setEpochs] = useState(8);
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");

  const loadLists = async () => {
    const [s, v, d, m] = await Promise.all([
      get<FtStatus>("/api/finetune/status"), get<Voice[]>("/api/voices"),
      get<DsSummary[]>("/api/finetune/datasets"), get<FtModel[]>("/api/finetune/models"),
    ]);
    setSt(s); setVoices(v); setSets(d); setModels(m);
    if (!srcVoice) setSrcVoice([...v].filter((x) => x.samples.length && !x.model).sort((a, b) => b.samples.length - a.samples.length)[0]?.id || "");
    if (s.defaults?.epochs) setEpochs((e) => e || s.defaults.epochs);
  };
  const open = async (id: string) => {
    const d = await get<Dataset>(`/api/finetune/datasets/${id}`);
    setDs(d);
    setName(`${d.name} (학습)`);
  };
  useEffect(() => { loadLists().catch((e) => setErr(String(e))); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);
  const running = models.find((m) => m.running);
  useEffect(() => {   // follow a running training
    if (!running) return;
    const t = window.setInterval(() => { loadLists().catch(() => undefined); }, 3000);
    return () => window.clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [running?.id]);

  const act = async (label: string, fn: () => Promise<unknown>) => {
    setBusy(label); setErr("");
    try { await fn(); } catch (e) { setErr(String(e).replace(/^Error: /, "")); } finally { setBusy(""); }
  };
  const fromVoice = () => act("클립을 모으는 중…", async () => {
    const s = await post<DsSummary>("/api/finetune/datasets/from-voice", { voice_id: srcVoice });
    await loadLists(); await open(s.id);
  });
  const fromFiles = () => act(transcribe ? "자르고 받아 적는 중… (10분 녹음이면 1~3분)" : "자르는 중…", async () => {
    if (!files?.length) throw new Error("녹음 파일을 골라 주세요.");
    const f = new FormData();
    Array.from(files).forEach((x) => f.append("files", x));
    f.append("name", recName || "학습 데이터"); f.append("voice_id", recVoice); f.append("transcribe", String(transcribe));
    const s = await postForm<DsSummary>("/api/finetune/datasets/from-recordings", f);
    await loadLists(); await open(s.id);
  });
  const editClip = async (c: Clip, body: Partial<Clip>) => {
    if (!ds) return;
    const nc = await patch<Clip>(`/api/finetune/datasets/${ds.id}/clips/${c.id}`, body);
    const clips = ds.clips.map((x) => (x.id === c.id ? nc : x));
    const used = clips.filter((x) => x.include && x.text);
    const counts = { included: used.length, confirmed: used.filter((x) => x.confirmed).length,
      minutes: Math.round(used.reduce((a, x) => a + x.duration, 0) / 6) / 10 };
    setDs({ ...ds, clips, ...counts });
    setSets((prev) => prev.map((x) => (x.id === ds.id ? { ...x, ...counts } : x)));
  };
  const train = () => act("학습을 시작하는 중…", async () => {
    if (!ds) return;
    await post("/api/finetune/train", { dataset_id: ds.id, name, epochs });
    await loadLists();
  });

  const minItems = st?.min_items ?? 5;
  const unconfirmed = ds ? ds.included - ds.confirmed : 0;
  return (
    <div className="cols">
      <div>
        <div className="panel">
          <h2>목소리 학습</h2>
          <p className="muted" style={{ marginTop: 0, lineHeight: 1.7 }}>
            한 사람의 목소리를 모아 학습하면, 10초짜리 참조 클립을 흉내 내는 것보다 그 사람의 억양과 말버릇이 더 잘 살아납니다.
            학습은 이 컴퓨터 안에서만 하고 녹음이 밖으로 나가지 않습니다. 끝나면 <b>목소리 목록에 새 목소리</b>로 들어가 녹음 만들기에서 고를 수 있습니다.
          </p>
          {st && !st.available && <div className="callout warn">{st.message}</div>}
          {st?.available && <div className="muted">학습 장치: {st.message}</div>}
          <div className="callout" style={{ marginTop: 10 }}>
            <b>녹음할 때</b>
            <ul style={{ margin: "6px 0 0", paddingLeft: 18, lineHeight: 1.7 }}>
              <li>본인 동의를 먼저 받고, 실제 환자 기록은 <b>가명으로 바꾼 뒤</b> 읽습니다. 녹음에 실제 환자 정보가 남으면 안 됩니다.</li>
              <li>읽기만 하지 말고 키워드만 보고 평소처럼 인계·구술하는 부분도 넣어야 말버릇이 학습됩니다. 10분이면 시험해 볼 수 있고 30분이면 더 좋습니다.</li>
              <li>조용한 방, 같은 마이크, 같은 거리로. 병동 소음은 녹음을 만들 때 따로 섞습니다.</li>
            </ul>
          </div>
        </div>

        <div className="panel">
          <h2>1. 학습 데이터 만들기</h2>
          <label>등록된 목소리의 클립으로</label>
          <div className="row">
            <div>
              <select value={srcVoice} onChange={(e) => setSrcVoice(e.target.value)}>
                {voices.filter((v) => v.samples.length && !v.model).map((v) => <option key={v.id} value={v.id}>{v.name} · 클립 {v.samples.length}개</option>)}
              </select>
            </div>
            <div className="narrow"><button onClick={fromVoice} disabled={!srcVoice || !!busy}>데이터 만들기</button></div>
          </div>
          <label style={{ marginTop: 12 }}>긴 녹음 파일로 (한 사람 목소리, 여러 파일 가능)</label>
          <div className="row">
            <div><input type="text" value={recName} onChange={(e) => setRecName(e.target.value)} placeholder="이름 (예: 간호사 B 구술)" /></div>
            <div>
              <select value={recVoice} onChange={(e) => setRecVoice(e.target.value)} title="학습한 목소리의 성별을 이 목소리에서 가져옵니다">
                <option value="">연결할 목소리 없음</option>
                {voices.filter((v) => !v.model).map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
              </select>
            </div>
          </div>
          <div className="row">
            <div><input type="file" accept="audio/*,.m4a,.wav,.mp3" multiple onChange={(e) => setFiles(e.target.files)} /></div>
            <div className="narrow"><label><input type="checkbox" checked={transcribe} onChange={(e) => setTranscribe(e.target.checked)} /> Whisper로 받아 적기</label></div>
            <div className="narrow"><button onClick={fromFiles} disabled={!files?.length || !!busy}>올리고 자르기</button></div>
          </div>
          {busy && <div className="muted" style={{ marginTop: 8 }}>{busy}</div>}
          {err && <div className="callout warn" style={{ marginTop: 8 }}>{err}</div>}

          <h3 style={{ marginTop: 16 }}>학습 데이터</h3>
          <table className="items" style={{ width: "100%" }}>
            <thead><tr><th>이름</th><th>클립</th><th>분</th><th>확인</th><th /></tr></thead>
            <tbody>
              {sets.map((s) => (
                <tr key={s.id} onClick={() => open(s.id)} style={{ cursor: "pointer", background: ds?.id === s.id ? "rgba(56,189,248,0.12)" : undefined }}>
                  <td><b>{s.name}</b></td>
                  <td className="muted">{s.included}/{s.items}</td>
                  <td className="muted">{s.minutes}</td>
                  <td className="muted">{s.confirmed}/{s.included}</td>
                  <td><button className="small danger" onClick={(e) => { e.stopPropagation(); act("삭제 중…", async () => { await del(`/api/finetune/datasets/${s.id}`); if (ds?.id === s.id) setDs(null); await loadLists(); }); }}>삭제</button></td>
                </tr>
              ))}
              {!sets.length && <tr><td colSpan={5} className="muted">아직 학습 데이터가 없습니다.</td></tr>}
            </tbody>
          </table>
        </div>

        <div className="panel">
          <h2>학습한 목소리</h2>
          <table className="items" style={{ width: "100%" }}>
            <thead><tr><th>이름</th><th>상태</th><th title="학습 / 떼어 둔 검증 클립. 검증 손실이 가장 낮은 회차를 저장합니다">손실</th><th /></tr></thead>
            <tbody>
              {models.map((m) => (
                <tr key={m.id}>
                  <td><b>{m.name}</b><div className="muted" style={{ fontSize: 12 }}>{new Date(m.created * 1000).toLocaleString()}</div></td>
                  <td>
                    {STAGE[m.stage] || m.stage}
                    {m.running && m.steps ? ` · ${m.epoch}/${m.epochs}회 · ${Math.round(((m.step || 0) / m.steps) * 100)}% · 남은 시간 ${mmss(m.eta_s)}` : ""}
                    {m.stage === "done" && m.best_epoch ? ` · ${m.best_epoch}/${m.epochs}회째 결과 사용` : ""}
                    {m.stage === "done" && m.minutes ? ` · ${m.minutes}분 걸림` : ""}
                    {(m.stage === "error" || m.stage === "cancelled") && m.message && <div className="muted" style={{ fontSize: 12 }}>{m.message}</div>}
                    {m.running && m.steps ? <div className="progress"><div style={{ width: `${((m.step || 0) / m.steps) * 100}%` }} /></div> : null}
                  </td>
                  <td className="muted">{[m.loss, m.val_loss].filter((x) => x != null).join(" / ")}</td>
                  <td>
                    {m.running
                      ? <button className="small" onClick={() => act("취소 중…", async () => { await post(`/api/finetune/models/${m.id}/cancel`); await loadLists(); })}>취소</button>
                      : <button className="small danger" onClick={() => act("삭제 중…", async () => { await del(`/api/finetune/models/${m.id}`); await loadLists(); })} title="학습 결과와 목소리 목록의 항목을 지웁니다">삭제</button>}
                  </td>
                </tr>
              ))}
              {!models.length && <tr><td colSpan={4} className="muted">아직 학습한 목소리가 없습니다.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>

      <div>
        {ds ? (
          <>
            <div className="panel">
              <h2>2. {ds.name} — 전사 확인</h2>
              <div className="callout">
                <b>말하려던 대로가 아니라 들리는 그대로</b> 적어 주세요. "어", "음", 고쳐 말한 부분도 그대로 둡니다.
                숫자와 영어 약어는 소리 나는 대로 한글로 적습니다(예: 비피 백이십에 팔십). 다 들어 보고 맞으면 <b>확인</b>에 체크합니다.
              </div>
              <div className="muted" style={{ margin: "8px 0" }}>쓰는 클립 {ds.included}개 · {ds.minutes}분 · 확인 {ds.confirmed}개</div>
              <div style={{ maxHeight: 560, overflowY: "auto" }}>
                {ds.clips.map((c, k) => (
                  <div key={c.id} style={{ borderTop: "1px solid rgba(148,163,184,0.2)", padding: "8px 0", opacity: c.include ? 1 : 0.5 }}>
                    <div className="row" style={{ alignItems: "center" }}>
                      <div className="narrow muted">{k + 1}</div>
                      <div><audio controls preload="none" src={apiUrl(`/api/finetune/datasets/${ds.id}/clips/${c.id}/audio`)} style={{ width: "100%", height: 32 }} /></div>
                      <div className="narrow muted">{c.duration.toFixed(1)}초</div>
                      <div className="narrow"><label><input type="checkbox" checked={c.include} onChange={(e) => editClip(c, { include: e.target.checked })} /> 쓰기</label></div>
                      <div className="narrow"><label><input type="checkbox" checked={c.confirmed} onChange={(e) => editClip(c, { confirmed: e.target.checked })} /> 확인</label></div>
                    </div>
                    <textarea defaultValue={c.text} rows={2} style={{ width: "100%", marginTop: 4 }} placeholder="들리는 그대로 적어 주세요"
                      onBlur={(e) => { if (e.target.value.trim() !== c.text) editClip(c, { text: e.target.value }); }} />
                  </div>
                ))}
              </div>
            </div>

            <div className="panel">
              <h2>3. 학습 시작</h2>
              <div className="row">
                <div><label>학습한 목소리 이름</label><input type="text" value={name} onChange={(e) => setName(e.target.value)} /></div>
                <div className="narrow"><label>학습 횟수</label><input type="number" min={1} max={30} value={epochs} onChange={(e) => setEpochs(Number(e.target.value) || 1)} style={{ width: 70 }} /></div>
              </div>
              <p className="muted" style={{ lineHeight: 1.7 }}>
                Apple GPU에서 6분 분량이면 한 번에 약 1분, NVIDIA GPU에서는 그보다 빠릅니다. 학습 중에는 녹음을 만들 수 없습니다.
              </p>
              {ds.included < minItems && <div className="callout warn">전사가 있는 클립이 {minItems}개 이상 있어야 합니다.</div>}
              {ds.included >= minItems && unconfirmed > 0 && <div className="callout">아직 확인하지 않은 클립이 {unconfirmed}개 있습니다. 틀린 전사는 학습을 망치니 들어 보고 시작하는 것이 좋습니다.</div>}
              <button className="primary" onClick={train} disabled={!st?.available || !!running || ds.included < minItems || !!busy} style={{ marginTop: 8 }}>
                {running ? "다른 학습이 진행 중입니다" : "학습 시작"}
              </button>
            </div>
          </>
        ) : (
          <div className="panel"><h2>전사 확인</h2><div className="muted">왼쪽에서 학습 데이터를 만들거나 골라 주세요.</div></div>
        )}
      </div>
    </div>
  );
}
