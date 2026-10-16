import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import FieldInput from "../components/FieldInput";
import JobProgress from "../components/JobProgress";
import NoisePanel from "../components/NoisePanel";
import AugmentPanel from "../components/AugmentPanel";
import PatientPanel from "../components/PatientPanel";
import SignalSelect from "../components/SignalSelect";
import Visualizer from "../components/Visualizer";
import { useEnergy } from "../lib/energy";
import VoiceDemo from "../components/VoiceDemo";
import { setHandoff, takeHandoff, ScriptHandoff } from "../lib/scriptStore";
import { apiUrl, AugmentSettings, DEFAULT_AUGMENT, DEFAULT_NOISE, DEFAULT_PATIENT, get, Job, NoiseSettings, nowLocalIso, Patient, post, put, Settings, TemplateSchema, Voice } from "../lib/api";
import { AppStatus } from "../lib/onboarding";
import { Tab } from "../components/Sidebar";

interface Preview {
  signal_format?: string;
  signal_parse?: { ok: boolean; name?: string; kind?: string; datetime?: string | null; format?: string; missing?: string[] | null };
  spoken_text: string;
  tts_text: string;
  signal: string;
  seed: number;
  filename: string;
  llm_polished: boolean;
}

interface Props {
  status?: AppStatus;
  onTab?: (t: Tab) => void;
}

export default function RecordPage({ status, onTab }: Props) {
  const [templates, setTemplates] = useState<TemplateSchema[]>([]);
  const [tkey, setTkey] = useState("s1");
  const [form, setForm] = useState<Record<string, unknown>>({});
  const [patient, setPatient] = useState<Patient>(DEFAULT_PATIENT);
  const [when, setWhen] = useState(nowLocalIso());
  const [style, setStyle] = useState("formal");
  const [seed, setSeed] = useState<number | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [edited, setEdited] = useState<string | null>(null);
  const [llm, setLlm] = useState(false);
  const [noise, setNoise] = useState<NoiseSettings>(DEFAULT_NOISE);
  const [rounds, setRounds] = useState(false);
  const [augment, setAugment] = useState<AugmentSettings>(DEFAULT_AUGMENT);
  const [disfluency, setDisfluency] = useState<number | "random">(0);
  const [variants, setVariants] = useState(1);
  const [signalFormat, setSignalFormat] = useState("");
  const [signalAliases, setSignalAliases] = useState<boolean | null>(null);
  const [voices, setVoices] = useState<Voice[]>([]);
  const [voiceId, setVoiceId] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [result, setResult] = useState<Job | null>(null);
  const [err, setErr] = useState("");
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [settings, setSettings] = useState<Settings | null>(null);
  const debounce = useRef<number | null>(null);
  const handoff = useRef<ScriptHandoff | null>(takeHandoff());   // from the review page: "이 대본으로 녹음 만들기"
  const setEnergy = useEnergy();

  const template = useMemo(() => templates.find((t) => t.key === tkey), [templates, tkey]);

  useEffect(() => {
    (async () => {
      try {
        const ts = await get<TemplateSchema[]>("/api/templates");
        setTemplates(ts);
        const vs = await get<Voice[]>("/api/voices");
        setVoices(vs);
        const first = vs.find((v) => v.samples.length);
        if (first) setVoiceId((cur) => cur || first.id);
        const s = await get<Settings>("/api/settings");
        setSettings(s);
        setStyle(handoff.current?.style || s.default_style || "formal");
        setNoise((n) => ({ ...n, level: s.noise_default_level ?? n.level }));
        if (handoff.current) {
          setTkey(handoff.current.template);
          setPatient(handoff.current.patient);
          setWhen(handoff.current.datetime);
        }
      } catch (e) {
        setErr("백엔드에 연결할 수 없습니다. 설정 탭에서 상태를 확인하세요.");
      }
    })();
  }, []);

  useEffect(() => {
    if (!tkey) return;
    get<Record<string, unknown>>(`/api/templates/${tkey}/defaults`).then((d) => {
      const h = handoff.current;
      if (h && h.template === tkey) {   // keep the reviewed script: same form, seed and edits
        handoff.current = null;
        setForm(h.form);
        setSeed(h.seed);
        setEdited(h.text_override ?? null);
        return;
      }
      setForm(d);
      setEdited(null);
    }).catch(() => undefined);
  }, [tkey]);

  const refreshVoices = () => get<Voice[]>("/api/voices").then((vs) => { setVoices(vs); const first = vs.find((v) => v.samples.length); if (first) setVoiceId((cur) => cur || first.id); }).catch(() => undefined);
  const useSystemVoice = async () => {
    try { setSettings(await put<Settings>("/api/settings", { tts_engine: "system" })); } catch (e) { setErr(String(e)); }
  };

  const doPreview = useCallback(async (opts?: { newSeed?: boolean; llm?: boolean }) => {
    if (!template) return;
    const s = opts?.newSeed ? null : seed;
    try {
      const p = await post<Preview>("/api/script/preview", {
        template: tkey, form, patient, datetime: when, style, seed: s, llm_polish: opts?.llm ?? false,
        signal_format: signalFormat || undefined, signal_aliases: signalAliases ?? undefined,
      });
      setPreview(p);
      setSeed(p.seed);
      setEdited(null);
      setErr("");
    } catch (e) {
      setErr(String(e));
    }
  }, [template, tkey, form, patient, when, style, seed, signalFormat, signalAliases]);

  // auto preview on changes (debounced), keeping the seed so edits are stable
  useEffect(() => {
    if (!template) return;
    if (debounce.current) window.clearTimeout(debounce.current);
    debounce.current = window.setTimeout(() => doPreview(), 250);
    return () => {
      if (debounce.current) window.clearTimeout(debounce.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form, patient, when, style, tkey, template, signalFormat, signalAliases]);

  const randomize = async () => {
    const r = await post<{ patient: Patient; form: Record<string, unknown>; datetime: string }>("/api/random-patient", { template: tkey });
    setPatient(r.patient);
    setForm(r.form);
    setWhen(r.datetime);
    setSeed(null);
  };

  const generate = async () => {
    setErr("");
    setResult(null);
    try {
      const job = await post<Job>("/api/generate", {
        template: tkey, form, patient, datetime: when, style, seed, llm_polish: llm && !edited,
        voice_id: voiceId, noise, rounds_voice: rounds, text_override: edited ?? undefined,
        augment, disfluency: disfluency === "random" ? 1 : disfluency, variants,
        signal_format: signalFormat || undefined, signal_aliases: signalAliases ?? undefined,
      });
      setJobId(job.id);
    } catch (e) {
      setErr(String(e));
    }
  };

  const renderSection = (s: TemplateSchema["sections"][number], protocol = false) => {
    const isCollapsed = collapsed[s.key] ?? protocol;
    const checked = protocol ? s.fields.filter((f) => f.kind === "bool" && form[f.key]).length : 0;
    return (
      <div className="section" key={s.key}>
        <div className="section-head" onClick={() => setCollapsed((c) => ({ ...c, [s.key]: !isCollapsed }))}>
          <strong>{isCollapsed ? "▸" : "▾"} {s.title}<span className="hint">{s.hint}</span></strong>
          {protocol && checked > 0 && <span className="badge ok">{checked}개 체크</span>}
        </div>
        {!isCollapsed && (
          <div className={s.fields.length > 3 ? "grid2" : ""}>
            {s.fields.map((f) => (
              <FieldInput key={f.key} field={f} value={form[f.key]} onChange={(v) => setForm((prev) => ({ ...prev, [f.key]: v }))} />
            ))}
          </div>
        )}
      </div>
    );
  };

  const selectedEngineClones = settings ? settings.tts_engine !== "silent" && settings.tts_engine !== "system" : true;
  const doneItem = result?.items[0];
  const wavRel = doneItem?.files?.wav ? doneItem.files.wav.split(/[\\/]/).slice(-1)[0] : "";

  return (
    <div className="cols">
      <div>
        <div className="panel">
          <h2><span className="step-badge">1</span> 기록 종류 <span className="hint">어떤 간호기록을 읽을지 고릅니다</span></h2>
          <div className="checks">
            {templates.map((t) => (
              <label key={t.key}>
                <input type="radio" name="tpl" checked={tkey === t.key} onChange={() => setTkey(t.key)} /> {t.title}
              </label>
            ))}
          </div>
          {template && <div className="muted" style={{ marginTop: 6 }}>{template.description} · 시그널 기록종류: <b>{template.signal_kind}</b></div>}
          <SignalSelect value={signalFormat} onChange={setSignalFormat} aliases={signalAliases} onAliases={setSignalAliases} />
          <div className="row" style={{ marginTop: 10 }}>
            <div>
              <label>시그널 발화 시각 (파일명에 사용)</label>
              <input type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} />
            </div>
            <div className="narrow">
              <button onClick={() => setWhen(nowLocalIso())}>지금</button>
            </div>
            <div>
              <label>말투</label>
              <select value={style} onChange={(e) => setStyle(e.target.value)}>
                <option value="formal">격식체 위주 (~하였습니다, 기본)</option>
                <option value="mixed">현장 혼합</option>
                <option value="casual">구어체 위주 (~하시구요)</option>
                <option value="chart">기록체 (~함/~됨, 차팅하듯)</option>
              </select>
            </div>
          </div>
        </div>

        <PatientPanel patient={patient} onChange={setPatient} onRandom={randomize} step={2} />

        <div className="panel">
          <h2><span className="step-badge">3</span> 환자 상태 체크 <span className="hint">체크/선택한 항목만 발화됩니다 · 비워 두면 기본 상태로 읽습니다</span></h2>
          {template?.sections.filter((s) => s.group !== "protocol").map((s) => renderSection(s))}
        </div>

        <div className="panel">
          <h2><span className="step-badge">4</span> 간호 프로토콜 체크리스트 <span className="hint">정규 차팅 · 간호진단별 중재 항목, 체크한 항목이 "~함" 기록체 또는 선택한 말투로 발화됩니다</span>
            <span style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
              <button className="small" onClick={() => setCollapsed((c) => { const n = { ...c }; template?.sections.filter((x) => x.group === "protocol").forEach((x) => { n[x.key] = false; }); return n; })}>모두 펼치기</button>
              <button className="small" onClick={() => setCollapsed((c) => { const n = { ...c }; template?.sections.filter((x) => x.group === "protocol").forEach((x) => { n[x.key] = true; }); return n; })}>모두 접기</button>
              <button className="small danger" onClick={() => setForm((prev) => { const n = { ...prev }; template?.sections.filter((x) => x.group === "protocol").forEach((x) => x.fields.forEach((f) => { if (f.kind === "bool") delete n[f.key]; })); return n; })}>체크 해제</button>
            </span>
          </h2>
          {template?.sections.filter((s) => s.group === "protocol").map((s) => renderSection(s, true))}
        </div>
      </div>

      <div>
        <div className="panel">
          <h2>
            <span className="step-badge">5</span> 대본 미리보기
            <span className="hint">왼쪽 선택에 따라 자동으로 바뀝니다 · 직접 고쳐도 됩니다</span>
            <span style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
              <button className="small" title="말투 바꾸기, LLM 다듬기, 발음 텍스트, 문장 표시는 대본 검토 단계에서"
                onClick={() => { setHandoff({ template: tkey, form, patient, datetime: when, style, seed, text_override: edited }); onTab?.("review"); }}>🔍 대본 검토에서 열기</button>
            </span>
          </h2>
          {preview ? (
            <textarea
              className="preview"
              rows={10}
              value={edited ?? preview.spoken_text}
              onChange={(e) => setEdited(e.target.value)}
              spellCheck={false}
            />
          ) : (
            <div className="preview muted">대본이 여기에 표시됩니다…</div>
          )}
          <div className="muted" style={{ marginTop: 6 }}>
            {edited !== null ? <span className="badge warn">직접 수정됨 — 수정한 텍스트가 그대로 녹음·저장됩니다</span> : preview?.llm_polished ? <span className="badge">LLM 다듬기 적용됨</span> : "대본을 직접 고쳐도 됩니다 (첫 줄 시그널은 형식을 유지하세요)."}
            {preview && <> · 파일명: <b>{preview.filename}.wav</b> / .txt / .json</>}
            {preview?.signal_parse && (preview.signal_parse.ok
              ? <> · <span className="badge ok">시그널 인식 ✔ {preview.signal_parse.name} / {preview.signal_parse.kind} / {preview.signal_parse.datetime}</span></>
              : <> · <span className="badge bad">시그널 인식 실패 (누락: {(preview.signal_parse.missing || []).join(", ")})</span></>)}
          </div>
        </div>

        <details className="adv">
          <summary><span className="step-badge">6</span><span className="lbl">소리 옵션</span> <span className="hint">병동 소음 · 녹음 장비 다양화 · 구어 흐트러짐 (기본값으로 두어도 됩니다){noise.enabled ? " · 소음 켜짐" : ""}{augment.enabled ? " · 증강 켜짐" : ""}</span></summary>
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
          <h2><span className="step-badge">7</span> 녹음 생성 <span className="hint">wav + 정답 txt + json이 출력 폴더에 저장됩니다</span></h2>
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
                  <option key={v.id} value={v.id} disabled={!v.samples.length}>{v.name} ({v.samples.length}개 샘플)</option>
                ))}
              </select>
              <div style={{ marginTop: 4 }}><VoiceDemo voiceId={voiceId} disabled={!voiceId} initialPitch={voices.find((v) => v.id === voiceId)?.pitch ?? 0} initialTempo={voices.find((v) => v.id === voiceId)?.tempo ?? 1} /></div>
            </div>
            <div className="narrow">
              <label>변형 수</label>
              <input type="number" min={1} max={20} value={variants} onChange={(e) => setVariants(Math.max(1, Math.min(20, Number(e.target.value))))} style={{ width: 70 }} title="같은 체크 상태로 말투·소음이 다른 녹음을 여러 개 생성" />
            </div>
            <div className="narrow">
              <label>
                <input type="checkbox" checked={llm} disabled={!settings || settings.llm_provider === "none" || edited !== null} onChange={(e) => setLlm(e.target.checked)} /> 생성 시 LLM 다듬기
              </label>
            </div>
            <div className="narrow">
              <button className="primary" onClick={generate} disabled={!preview || (selectedEngineClones && !voiceId)}>🎙 발화 + 녹음 저장{variants > 1 ? ` ×${variants}` : ""}</button>
            </div>
          </div>
          {!selectedEngineClones && <div className="muted">현재 엔진({status?.engineLabel || settings?.tts_engine})은 목소리를 복제하지 않습니다. 등록한 목소리로 만들려면 설정에서 복제 엔진을 고르세요.</div>}
          {err && <div className="error">{err}</div>}
          <JobProgress jobId={jobId} onDone={(j) => { setResult(j); }} />
          {result && result.total > 1 && (
            <ul className="list" style={{ marginTop: 8 }}>
              {result.items.map((i) => (
                <li key={i.index}><div className="grow">{i.files?.wav?.split(/[\\/]/).pop()} <span className="muted">{i.duration}s</span></div>{i.status === "error" ? <span className="badge bad" title={i.error}>오류</span> : <span className="badge ok">완료</span>}</li>
              ))}
            </ul>
          )}
          {doneItem?.status === "done" && (
            <div style={{ marginTop: 8 }}>
              <div className="ok-text">저장됨: {doneItem.files.wav} ({doneItem.duration}s)</div>
              <Visualizer autoPlay onEnergy={setEnergy} src={apiUrl(`/api/output/file?rel=${encodeURIComponent(doneItem.files.wav.replace(result!.folder || "", "").replace(/^[\\/]/, ""))}`) + `&t=${result!.created}`} />
              <div className="row" style={{ marginTop: 6 }}>
                <div className="narrow"><button onClick={() => window.nursing?.showInFolder(doneItem.files.wav)}>폴더에서 보기</button></div>
                <div className="narrow muted">{wavRel}</div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
