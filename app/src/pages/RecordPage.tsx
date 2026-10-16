import { useEffect, useState } from "react";
import JobProgress from "../components/JobProgress";
import NoisePanel from "../components/NoisePanel";
import AugmentPanel from "../components/AugmentPanel";
import Visualizer from "../components/Visualizer";
import { useEnergy } from "../lib/energy";
import VoiceDemo from "../components/VoiceDemo";
import Term from "../components/Term";
import { BasketItem, clearBasket, getBasket, removeFromBasket, updateBasketText } from "../lib/scriptStore";
import { apiUrl, AugmentSettings, DEFAULT_AUGMENT, DEFAULT_NOISE, get, Job, NoiseSettings, post, put, Settings, Voice } from "../lib/api";
import { AppStatus } from "../lib/onboarding";
import { Tab } from "../components/Sidebar";

interface Props {
  status?: AppStatus;
  onTab?: (t: Tab) => void;
}

const STYLES: Record<string, string> = { formal: "격식체", mixed: "현장 혼합", casual: "구어체", chart: "기록체" };

/** 3 · 녹음 만들기 (2026-10-17 split): the scripts come from the basket that 2 · 대본 생성 filled; this page only
 *  chooses the voice, the sound options and starts the recordings. */
export default function RecordPage({ status, onTab }: Props) {
  const [basket, setBasket] = useState<BasketItem[]>(getBasket());
  const [checked, setChecked] = useState<Set<string>>(new Set(getBasket().map((b) => b.id)));
  const [cur, setCur] = useState<string>(getBasket().slice(-1)[0]?.id || "");
  const [style, setStyle] = useState("");
  const [llm, setLlm] = useState(false);
  const [noise, setNoise] = useState<NoiseSettings>(DEFAULT_NOISE);
  const [rounds, setRounds] = useState(false);
  const [augment, setAugment] = useState<AugmentSettings>(DEFAULT_AUGMENT);
  const [disfluency, setDisfluency] = useState<number | "random">(0);
  const [variants, setVariants] = useState(1);
  const [voices, setVoices] = useState<Voice[]>([]);
  const [voiceId, setVoiceId] = useState("");
  const [patientVoice, setPatientVoice] = useState("auto");   // dialogue scripts: who reads the patient's lines
  const [jobId, setJobId] = useState<string | null>(null);
  const [result, setResult] = useState<Job | null>(null);
  const [err, setErr] = useState("");
  const [settings, setSettings] = useState<Settings | null>(null);
  const setEnergy = useEnergy();

  useEffect(() => {
    (async () => {
      try {
        const vs = await get<Voice[]>("/api/voices");
        setVoices(vs);
        const first = vs.find((v) => v.samples.length);
        if (first) setVoiceId((c) => c || first.id);
        const s = await get<Settings>("/api/settings");
        setSettings(s);
        setNoise((n) => ({ ...n, level: s.noise_default_level ?? n.level }));
      } catch {
        setErr("백엔드에 연결할 수 없습니다. 설정 탭에서 상태를 확인하세요.");
      }
    })();
  }, []);
  const refreshVoices = () => get<Voice[]>("/api/voices").then((vs) => { setVoices(vs); const first = vs.find((v) => v.samples.length); if (first) setVoiceId((c) => c || first.id); }).catch(() => undefined);
  const useSystemVoice = async () => {
    try { setSettings(await put<Settings>("/api/settings", { tts_engine: "system" })); } catch (e) { setErr(String(e)); }
  };

  const current = basket.find((b) => b.id === cur);
  const selected = basket.filter((b) => checked.has(b.id));
  const toggle = (id: string) => setChecked((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const remove = (id: string) => { setBasket(removeFromBasket(id)); setChecked((s) => { const n = new Set(s); n.delete(id); return n; }); if (cur === id) setCur(""); };

  const generate = async () => {
    setErr("");
    setResult(null);
    const specs: Record<string, unknown>[] = [];
    for (const b of selected) {
      for (let i = 0; i < Math.max(1, variants); i++) {
        specs.push({ template: b.template, form: b.form, patient: b.patient, datetime: b.datetime, style: style || b.style, dialogue: !!b.dialogue,
          seed: i === 0 ? b.seed : null, text_override: i === 0 ? (b.text_override ?? undefined) : undefined });   // variant 2+ : new wording, same facts
      }
    }
    if (!specs.length) return;
    try {
      const job = await post<Job>("/api/generate/specs", {
        specs, voice_id: voiceId, patient_voice_id: patientVoice, noise, rounds_voice: rounds, augment, disfluency: disfluency === "random" ? "random" : disfluency,
        llm_polish: llm, signal_format: "strict",
      });
      setJobId(job.id);
    } catch (e) {
      setErr(String(e));
    }
  };

  const selectedEngineClones = settings ? settings.tts_engine !== "silent" && settings.tts_engine !== "system" : true;
  const done = result?.items.filter((i) => i.status === "done") ?? [];
  const firstWav = done[0]?.files?.wav;

  return (
    <div className="cols">
      <div>
        <div className="panel">
          <h2><span className="step-badge">1</span> 🧺 대본 바구니 <span className="hint">{basket.length}개 · 체크한 대본이 녹음됩니다 · 대본은 2 · 대본 생성에서 만듭니다</span>
            <span style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
              <button className="small" onClick={() => onTab?.("review")}>＋ 대본 더 담기</button>
              <button className="small" onClick={() => setChecked(new Set(basket.map((b) => b.id)))} disabled={!basket.length}>모두 선택</button>
              <button className="small danger" disabled={!basket.length} onClick={() => { if (confirm("바구니를 비울까요?")) { clearBasket(); setBasket([]); setChecked(new Set()); setCur(""); } }}>비우기</button>
            </span>
          </h2>
          {basket.length ? (
            <table className="items">
              <thead><tr><th></th><th>기록 종류</th><th>환자</th><th>말투</th><th>길이</th><th>⚠</th><th></th></tr></thead>
              <tbody>
                {basket.map((b) => (
                  <tr key={b.id} onClick={() => setCur(b.id)} style={{ cursor: "pointer", background: cur === b.id ? "rgba(56,189,248,0.12)" : undefined }}>
                    <td><input type="checkbox" checked={checked.has(b.id)} onChange={() => toggle(b.id)} onClick={(e) => e.stopPropagation()} /></td>
                    <td>{b.record_kind}{b.dialogue ? " 💬" : ""}</td><td>{b.patient.name}</td><td className="muted">{STYLES[b.style] || b.style}</td>
                    <td className="muted">{b.spoken_text.length}자{b.text_override != null ? " ✎" : ""}</td>
                    <td>{b.issues.length ? <span className="badge bad" title={b.issues.join("\n")}>{b.issues.length}</span> : ""}</td>
                    <td><button className="small danger" onClick={(e) => { e.stopPropagation(); remove(b.id); }}>빼기</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="empty">
              <b>바구니가 비어 있습니다</b>
              2 · 대본 생성에서 대본을 만들어 읽어 보고 "🧺 바구니에 담기"를 누르면 여기에 쌓입니다.
              <div className="row"><div className="narrow"><button className="primary" onClick={() => onTab?.("review")}>대본 생성으로 가기</button></div></div>
            </div>
          )}
        </div>

        <div className="panel">
          <h2><span className="step-badge">2</span> 대본 확인 <span className="hint">고르면 보입니다 · 여기서 고친 텍스트가 그대로 녹음·정답이 됩니다</span></h2>
          {current ? (
            <>
              <div className="muted" style={{ marginBottom: 6 }}><span className="badge">{current.record_kind}</span> {current.patient.name} · {current.patient.diagnosis} {current.patient.surgery || current.patient.regimen || ""} · {STYLES[current.style] || current.style}</div>
              <textarea className="preview" rows={12} spellCheck={false} value={current.text_override ?? current.spoken_text}
                onChange={(e) => setBasket(updateBasketText(current.id, e.target.value))} />
              <div className="muted" style={{ marginTop: 6 }}>
                {current.issues.length ? <span className="badge bad" title={current.issues.join("\n")}>⚠ 모순 {current.issues.length}: {current.issues[0]}</span> : null}
                {current.text_override != null ? <span className="badge warn" style={{ marginLeft: 6 }}>직접 수정됨 — 첫 줄 시그널은 형식을 유지하세요</span> : " 말투·문구를 바꾸려면 대본 생성에서 다시 담으세요."}
              </div>
            </>
          ) : (
            <div className="preview muted">바구니에서 대본을 고르면 여기에 표시됩니다…</div>
          )}
        </div>
      </div>

      <div>
        <details className="adv" open>
          <summary><span className="step-badge">3</span><span className="lbl">소리 옵션</span> <span className="hint">병동 소음 · 녹음 장비 다양화 · 구어 <Term k="흐트러짐" /> (기본값으로 두어도 됩니다){noise.enabled ? " · 소음 켜짐" : ""}{augment.enabled ? " · 증강 켜짐" : ""}</span></summary>
          <div className="inner">
            <NoisePanel
              value={noise}
              onChange={setNoise}
              voiceId={voiceId}
              extra={
                <label title="등록된 다른 목소리로 회진 대화를 합성해 멀리서 들리게 섞습니다 (목소리 2개 이상 필요)">
                  <input type="checkbox" checked={rounds} onChange={(e) => setRounds(e.target.checked)} /> 다른 환자 회진 음성 (TTS)
                </label>
              }
            />
            <AugmentPanel value={augment} onChange={setAugment} disfluency={disfluency} onDisfluency={setDisfluency} />
          </div>
        </details>

        <div className="panel highlight">
          <h2><span className="step-badge">4</span> 녹음 생성 <span className="hint">wav + 정답 txt + json이 출력 폴더에 저장됩니다</span></h2>
          {selectedEngineClones && !voices.some((v) => v.samples.length) && (
            <div className="empty" style={{ marginBottom: 12 }}>
              <b>아직 등록된 간호사 목소리가 없습니다</b>
              목소리를 등록하면 그 목소리로 녹음이 만들어집니다. 먼저 흐름만 확인하려면 이 PC의 시스템 음성으로 체험할 수 있습니다.
              <div className="row">
                <div className="narrow"><button className="primary" onClick={() => onTab?.("voices")}>목소리 등록하러 가기</button></div>
                <div className="narrow"><button onClick={useSystemVoice}>시스템 음성으로 체험하기</button></div>
              </div>
            </div>
          )}
          <div className="row">
            <div>
              <label>목소리 (등록된 간호사)</label>
              <select value={voiceId} onChange={(e) => setVoiceId(e.target.value)} onFocus={refreshVoices}>
                <option value="">— 선택 —</option>
                {voices.map((v) => (
                  <option key={v.id} value={v.id} disabled={!v.samples.length}>{v.name}</option>
                ))}
              </select>
              <div style={{ marginTop: 4 }}><VoiceDemo voiceId={voiceId} disabled={!voiceId} initialPitch={voices.find((v) => v.id === voiceId)?.pitch ?? 0} initialTempo={voices.find((v) => v.id === voiceId)?.tempo ?? 1} /></div>
            </div>
            {basket.some((b) => b.dialogue && checked.has(b.id)) && (
              <div>
                <label>환자 목소리 (💬 대화형 대본)</label>
                <select value={patientVoice} onChange={(e) => setPatientVoice(e.target.value)} title="환자 대답 줄을 읽을 목소리. 자동 = 환자 성별과 같은 등록 목소리(기본 음성 포함), 없으면 간호사 목소리를 낮춰서">
                  <option value="auto">자동 (환자 성별에 맞는 등록 목소리)</option>
                  <option value="same">간호사 목소리 변조 (남 −5·여 −2반음, 80세↑ 느리게)</option>
                  {voices.filter((v) => v.samples.length && v.id !== voiceId).map((v) => <option key={v.id} value={v.id}>{v.name}{v.sex ? ` (${v.sex})` : ""}</option>)}
                </select>
              </div>
            )}
            <div className="narrow">
              <label>말투</label>
              <select value={style} onChange={(e) => setStyle(e.target.value)} title="비우면 대본을 담을 때의 말투 그대로">
                <option value="">대본 그대로</option>
                {Object.entries(STYLES).map(([k, l]) => <option key={k} value={k}>{l}로 통일</option>)}
              </select>
            </div>
            <div className="narrow">
              <label><Term k="변형 수" /></label>
              <input type="number" min={1} max={20} value={variants} onChange={(e) => setVariants(Math.max(1, Math.min(20, Number(e.target.value))))} style={{ width: 70 }} title="대본마다 문구·소음이 다른 녹음을 여러 개 (첫 번째는 읽은 그대로)" />
            </div>
            <div className="narrow">
              <label>
                <input type="checkbox" checked={llm} disabled={!settings || settings.llm_provider === "none"} onChange={(e) => setLlm(e.target.checked)} /> 생성 시 <Term k="LLM 다듬기" />
              </label>
            </div>
            <div className="narrow">
              <button className="primary" onClick={generate} disabled={!selected.length || (selectedEngineClones && !voiceId)}>🎙 {selected.length}개 발화 + 녹음 저장{variants > 1 ? ` ×${variants}` : ""}</button>
            </div>
          </div>
          {!selectedEngineClones && <div className="muted">현재 엔진({status?.engineLabel || settings?.tts_engine})은 목소리를 복제하지 않습니다. 등록한 목소리로 만들려면 설정에서 복제 엔진을 고르세요.</div>}
          {err && <div className="error">{err}</div>}
          <JobProgress jobId={jobId} onDone={(j) => { setResult(j); }} />
          {result && (
            <ul className="list" style={{ marginTop: 8 }}>
              {result.items.map((i) => (
                <li key={i.index}><div className="grow">{i.files?.wav?.split(/[\\/]/).pop() || i.patient} <span className="muted">{i.duration ? `${i.duration}s` : ""}</span></div>{i.status === "error" ? <span className="badge bad" title={i.error}>오류</span> : i.status === "done" ? <span className="badge ok">완료</span> : <span className="muted">{i.status}</span>}</li>
              ))}
            </ul>
          )}
          {firstWav && (
            <div style={{ marginTop: 8 }}>
              <div className="ok-text">저장됨: {done.length}개 · {firstWav}</div>
              <Visualizer autoPlay onEnergy={setEnergy} src={apiUrl(`/api/output/file?rel=${encodeURIComponent(firstWav.replace(result!.folder || "", "").replace(/^[\\/]/, ""))}`) + `&t=${result!.created}`} />
              <div className="row" style={{ marginTop: 6 }}>
                <div className="narrow"><button onClick={() => window.nursing?.showInFolder(firstWav)}>폴더에서 보기</button></div>
                <div className="narrow"><button onClick={() => onTab?.("results")}>결과물 · 검수로 →</button></div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
