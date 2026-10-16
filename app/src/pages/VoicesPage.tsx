import { useEffect, useRef, useState } from "react";
import { apiUrl, del, EnrollScript, get, patch, post, postBlob, Voice } from "../lib/api";
import { Recorder, startRecording } from "../lib/wav";
import Visualizer from "../components/Visualizer";
import VoiceDemo from "../components/VoiceDemo";
import { useEnergy } from "../lib/energy";

export default function VoicesPage() {
  const [voices, setVoices] = useState<Voice[]>([]);
  const [sel, setSel] = useState<string>("");
  const [scripts, setScripts] = useState<EnrollScript[]>([]);
  const [scriptId, setScriptId] = useState<string>("");
  const [customText, setCustomText] = useState("");
  const [newName, setNewName] = useState("");
  const [newNote, setNewNote] = useState("");
  const [recorder, setRecorder] = useState<Recorder | null>(null);
  const [level, setLevel] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [busy, setBusy] = useState("");
  const [showClips, setShowClips] = useState(false);
  const [err, setErr] = useState("");
  const [testUrl, setTestUrl] = useState("");
  const [testNote, setTestNote] = useState("");
  const [msgLong, setMsgLong] = useState("");
  const timer = useRef<number | null>(null);
  const setEnergy = useEnergy();

  const load = async () => {
    const vs = await get<Voice[]>("/api/voices");
    setVoices(vs);
    if (!sel && vs.length) setSel(vs[0].id);
  };
  useEffect(() => {
    load().catch((e) => setErr(String(e)));
    get<EnrollScript[]>("/api/enroll-scripts").then((s) => {
      setScripts(s);
      if (s.length) setScriptId(s[0].id);
    }).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const voice = voices.find((v) => v.id === sel);
  const script = scripts.find((s) => s.id === scriptId);
  const transcript = scriptId === "__custom" ? customText : script?.text || "";
  const doneScripts = new Set(voice?.samples.map((s) => s.script_id));

  const create = async () => {
    if (!newName.trim()) return;
    const v = await post<Voice>("/api/voices", { name: newName, note: newNote });
    setNewName("");
    setNewNote("");
    await load();
    setSel(v.id);
  };

  const removeVoice = async (id: string) => {
    if (!confirm("이 목소리와 모든 샘플을 삭제할까요?")) return;
    await del(`/api/voices/${id}`);
    setSel("");
    await load();
  };

  const record = async () => {
    setErr("");
    try {
      const r = await startRecording((v) => { setLevel(v); setEnergy(Math.min(1, v * 6)); });
      setRecorder(r);
      setElapsed(0);
      const start = Date.now();
      timer.current = window.setInterval(() => setElapsed((Date.now() - start) / 1000), 100);
    } catch (e) {
      setErr("마이크를 사용할 수 없습니다: " + String(e));
    }
  };

  const stop = async () => {
    if (!recorder || !voice) return;
    if (timer.current) window.clearInterval(timer.current);
    const blob = await recorder.stop();
    setRecorder(null);
    setEnergy(0);
    await upload(blob, "recording.wav");
  };

  const upload = async (blob: Blob, filename: string) => {
    if (!voice) return;
    setBusy("샘플 저장 중…");
    try {
      const fd = new FormData();
      fd.append("file", blob, filename);
      fd.append("transcript", transcript);
      fd.append("script_id", scriptId === "__custom" ? "" : scriptId);
      const r = await fetch(apiUrl(`/api/voices/${voice.id}/samples`), { method: "POST", body: fd });
      if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
      await load();
      // move on to the next script not yet recorded
      const next = scripts.find((s) => s.id !== scriptId && !doneScripts.has(s.id));
      if (next && scriptId !== "__custom") setScriptId(next.id);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy("");
    }
  };

  const uploadLong = async (file: File) => {
    if (!voice) return;
    setErr("");
    setBusy("긴 녹음을 6~14초 조각으로 자르고 전사하는 중… (Whisper 설치 시 수십 초)");
    try {
      const fd = new FormData();
      fd.append("file", file, file.name);
      fd.append("max_clips", "8");
      fd.append("transcribe", "true");
      const r = await fetch(apiUrl(`/api/voices/${voice.id}/samples/from-long`), { method: "POST", body: fd });
      if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
      const j = await r.json();
      await load();
      setMsgLong(`${j.added.length}개 샘플 추가${j.transcribed ? " (자동 전사됨 — 내용을 확인해 고쳐 주세요)" : " (전사 없음 — faster-whisper 설치 시 자동 전사, 지금은 각 샘플의 대본을 직접 입력)"}`);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy("");
    }
  };

  const editTranscript = async (sid: string, text: string) => {
    if (!voice) return;
    await fetch(apiUrl(`/api/voices/${voice.id}/samples/${sid}`), { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ transcript: text }) });
    await load();
  };

  const removeSample = async (sid: string) => {
    if (!voice) return;
    await del(`/api/voices/${voice.id}/samples/${sid}`);
    await load();
  };

  const setPrimary = async (sid: string) => {
    if (!voice) return;
    await patch(`/api/voices/${voice.id}`, { primary_sample: sid });
    await load();
  };

  const testVoice = async () => {
    if (!voice) return;
    setBusy("합성 테스트 중… (모델 첫 로딩 시 수십 초)");
    setErr("");
    setTestUrl("");
    try {
      const { blob, headers } = await postBlob(`/api/voices/${voice.id}/test`, {});
      setTestUrl(URL.createObjectURL(blob));
      const clones = headers.get("X-Clones-Voice") === "True";
      setTestNote(clones ? `엔진: ${headers.get("X-Engine")} (목소리 복제)` : `엔진: ${headers.get("X-Engine")} — 복제 엔진이 아니라 등록한 목소리와 다릅니다`);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy("");
    }
  };

  return (
    <div className="cols">
      <div>
        {!voices.length && (
          <div className="callout">
            <b>처음이라면 이렇게 하세요</b>
            <ol style={{ margin: "6px 0 0", paddingLeft: 18, lineHeight: 1.8 }}>
              <li>아래에 목소리 이름(예: 간호사 A)을 적고 <b>＋ 추가</b></li>
              <li>오른쪽에 나오는 대본을 보고 <b>● 녹음 시작</b> → 8~15초 읽고 <b>■ 녹음 종료</b></li>
              <li>대본을 바꿔 가며 3개 정도 녹음하면 끝. 이미 녹음해 둔 파일이 있으면 "긴 녹음에서 샘플 자동 추출"</li>
            </ol>
          </div>
        )}
        <div className="panel">
          <h2>등록된 목소리</h2>
          <ul className="list">
            {voices.map((v) => (
              <li key={v.id} className={v.id === sel ? "active" : ""} onClick={() => setSel(v.id)} style={{ cursor: "pointer" }}>
                <div className="grow">
                  <b>{v.name}</b> <span className="muted">{v.note}</span>
                  <div className="muted">참조 클립 {v.samples.length}개 · {v.samples.reduce((a, s) => a + s.duration, 0).toFixed(0)}초</div>
                </div>
                <button className="small danger" onClick={(e) => { e.stopPropagation(); removeVoice(v.id); }}>삭제</button>
              </li>
            ))}
            {!voices.length && <li className="muted">아직 등록된 목소리가 없습니다.</li>}
          </ul>
          <div className="row" style={{ marginTop: 10 }}>
            <div>
              <label>새 목소리 이름 (예: 간호사 A)</label>
              <input type="text" value={newName} onChange={(e) => setNewName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && create()} />
            </div>
            <div>
              <label>메모</label>
              <input type="text" value={newNote} onChange={(e) => setNewNote(e.target.value)} placeholder="예: 30대 여, 외과 병동" />
            </div>
            <div className="narrow"><button className="primary" onClick={create}>＋ 추가</button></div>
          </div>
        </div>
        <div className="panel">
          <h2>녹음 요령</h2>
          <ul className="muted" style={{ margin: 0, paddingLeft: 18, lineHeight: 1.7 }}>
            <li>조용한 곳에서 마이크와 20~30cm 거리를 두고, 실제 기록을 구술하듯 자연스럽게 읽어 주세요.</li>
            <li>한 샘플은 <b>8~15초</b>가 가장 좋습니다 (너무 길면 복제 품질이 오히려 떨어집니다). 대본 하나 = 샘플 하나.</li>
            <li>샘플을 여러 개 등록하면 대량 생성 시 참조 음성이 번갈아 쓰여 녹음본이 더 다양해집니다. 3~5개 권장.</li>
            <li>대본과 다르게 읽었다면 아래 대본 텍스트를 실제 읽은 내용으로 고친 뒤 저장하세요 (모델이 전사를 참조합니다).</li>
          </ul>
        </div>
      </div>

      <div>
        {voice ? (
          <>
            <div className="panel">
              <h2>{voice.name} — 목소리 학습용 샘플 녹음</h2>
              <div className="row">
                <div>
                  <label>예시 대본 (의학용어 포함)</label>
                  <select value={scriptId} onChange={(e) => setScriptId(e.target.value)}>
                    {scripts.map((s) => (
                      <option key={s.id} value={s.id}>{doneScripts.has(s.id) ? "✓ " : ""}{s.title}</option>
                    ))}
                    <option value="__custom">직접 입력</option>
                  </select>
                </div>
              </div>
              {scriptId === "__custom" ? (
                <textarea rows={4} value={customText} onChange={(e) => setCustomText(e.target.value)} placeholder="읽을 문장을 입력하세요 (8~15초 분량)" />
              ) : (
                <div className="script-box">{script?.text}</div>
              )}
              <div className="row" style={{ marginTop: 12 }}>
                <div className="narrow">
                  {!recorder ? (
                    <button className="primary rec-btn" onClick={record} disabled={!transcript.trim() || !!busy}>● 녹음 시작</button>
                  ) : (
                    <button className="danger rec-btn live" onClick={stop}>■ 녹음 종료 및 저장 ({elapsed.toFixed(1)}s)</button>
                  )}
                </div>
                <div>
                  <div className="meter"><div style={{ width: `${Math.min(100, level * 400)}%` }} /></div>
                  <div className="muted">{recorder ? (elapsed > 15 ? "15초가 넘었습니다. 종료해 주세요." : "녹음 중… 대본을 읽어 주세요") : "입력 레벨"}</div>
                </div>
                <div className="narrow">
                  <label style={{ display: "inline-block" }}>
                    <span className="filebtn">파일로 추가</span>
                    <input type="file" accept="audio/*,.wav,.flac,.ogg,.mp3,.m4a,.aac,.webm" style={{ display: "none" }} disabled={!transcript.trim()}
                      onChange={(e) => e.target.files?.[0] && upload(e.target.files[0], e.target.files[0].name)} />
                  </label>
                </div>
              </div>
              <div className="row" style={{ marginTop: 10 }}>
                <div className="narrow">
                  <label style={{ display: "inline-block" }}>
                    <span className="filebtn">🎞 긴 녹음(2~3분)에서 샘플 자동 추출</span>
                    <input type="file" accept="audio/*,.wav,.flac,.ogg,.mp3,.m4a,.aac,.webm" style={{ display: "none" }} onChange={(e) => e.target.files?.[0] && uploadLong(e.target.files[0])} />
                  </label>
                </div>
                <div className="muted">실제 녹음한 간호기록 파일(m4a/mp3/wav)을 올리면 무음 구간 기준으로 6~14초 조각을 골라 샘플로 등록합니다. {msgLong}</div>
              </div>
              {busy && <div className="muted">{busy}</div>}
              {err && <div className="error">{err}</div>}
            </div>

            <div className="panel">
              <h2>이 목소리의 예시 <span className="hint">고정 문장을 이 목소리로 읽은 생성본 · 원음은 재생하지 않습니다</span></h2>
              <VoiceDemo voiceId={voice.id} disabled={!voice.samples.length} />
              <div className="row" style={{ marginTop: 10 }}>
                <div className="narrow"><button onClick={testVoice} disabled={!voice.samples.length || !!busy}>🔊 다른 문장으로 합성 테스트</button></div>
                <div className="muted">{testNote}</div>
              </div>
              {testUrl && <div style={{ marginTop: 10 }}><Visualizer autoPlay src={testUrl} onEnergy={setEnergy} height={120} /></div>}
            </div>

            <div className="panel">
              <h2>
                <button className="link" onClick={() => setShowClips(!showClips)} style={{ font: "inherit", padding: 0 }}>
                  {showClips ? "▾" : "▸"} 참조 클립 {voice.samples.length}개 · {voice.samples.reduce((a, s) => a + s.duration, 0).toFixed(0)}초
                </button>
                <span className="hint">복제에 쓰는 원음과 전사. 전사를 고치거나 잘못 잘린 클립을 지울 때만 펼치세요 ★ = 기본 참조</span>
              </h2>
              {showClips && <ul className="list">
                {voice.samples.map((s) => (
                  <li key={s.id}>
                    <button className="small" title="기본으로" onClick={() => setPrimary(s.id)}>{voice.primary_sample === s.id ? "★" : "☆"}</button>
                    <div className="grow">
                      <div><b>{scripts.find((x) => x.id === s.script_id)?.title || (s.script_id === "auto" ? "긴 녹음에서 추출" : "직접 입력")}</b> <span className="muted">{s.duration}s</span></div>
                      <input type="text" defaultValue={s.transcript} placeholder="이 샘플에서 실제로 말한 내용 (전사)" style={{ fontSize: 12, marginTop: 2 }}
                        onBlur={(e) => e.target.value !== s.transcript && editTranscript(s.id, e.target.value)} />
                      <audio controls preload="none" src={apiUrl(`/api/voices/${voice.id}/samples/${s.id}/audio`)} style={{ height: 28 }} />
                    </div>
                    <button className="small danger" onClick={() => removeSample(s.id)}>삭제</button>
                  </li>
                ))}
                {!voice.samples.length && <li className="muted">샘플이 없습니다. 위에서 대본을 읽어 녹음하세요.</li>}
              </ul>}
              {!showClips && !voice.samples.length && <div className="muted">아직 참조 클립이 없습니다. 위에서 대본을 읽어 녹음하거나 긴 녹음에서 추출하세요.</div>}
            </div>
          </>
        ) : (
          <div className="panel"><div className="empty"><b>왼쪽에서 목소리를 먼저 추가하세요</b>이름만 적고 ＋ 추가를 누르면 여기에 녹음 화면이 나타납니다.</div></div>
        )}
      </div>
    </div>
  );
}
