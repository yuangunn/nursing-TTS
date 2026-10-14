import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import FieldInput from "../components/FieldInput";
import JobProgress from "../components/JobProgress";
import NoisePanel from "../components/NoisePanel";
import PatientPanel from "../components/PatientPanel";
import Visualizer from "../components/Visualizer";
import { useEnergy } from "../lib/energy";
import { apiUrl, DEFAULT_NOISE, DEFAULT_PATIENT, get, Job, NoiseSettings, nowLocalIso, Patient, post, Settings, TemplateSchema, Voice } from "../lib/api";

interface Preview {
  spoken_text: string;
  tts_text: string;
  signal: string;
  seed: number;
  filename: string;
  llm_polished: boolean;
}

export default function RecordPage() {
  const [templates, setTemplates] = useState<TemplateSchema[]>([]);
  const [tkey, setTkey] = useState("s1");
  const [form, setForm] = useState<Record<string, unknown>>({});
  const [patient, setPatient] = useState<Patient>(DEFAULT_PATIENT);
  const [when, setWhen] = useState(nowLocalIso());
  const [style, setStyle] = useState("mixed");
  const [seed, setSeed] = useState<number | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [edited, setEdited] = useState<string | null>(null);
  const [llm, setLlm] = useState(false);
  const [noise, setNoise] = useState<NoiseSettings>(DEFAULT_NOISE);
  const [rounds, setRounds] = useState(false);
  const [voices, setVoices] = useState<Voice[]>([]);
  const [voiceId, setVoiceId] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [result, setResult] = useState<Job | null>(null);
  const [err, setErr] = useState("");
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [settings, setSettings] = useState<Settings | null>(null);
  const [showTts, setShowTts] = useState(false);
  const debounce = useRef<number | null>(null);
  const setEnergy = useEnergy();

  const template = useMemo(() => templates.find((t) => t.key === tkey), [templates, tkey]);

  useEffect(() => {
    (async () => {
      try {
        const ts = await get<TemplateSchema[]>("/api/templates");
        setTemplates(ts);
        setVoices(await get<Voice[]>("/api/voices"));
        const s = await get<Settings>("/api/settings");
        setSettings(s);
        setStyle(s.default_style || "mixed");
        setNoise((n) => ({ ...n, level: s.noise_default_level ?? n.level }));
      } catch (e) {
        setErr("백엔드에 연결할 수 없습니다. 설정 탭에서 상태를 확인하세요.");
      }
    })();
  }, []);

  useEffect(() => {
    if (!tkey) return;
    get<Record<string, unknown>>(`/api/templates/${tkey}/defaults`).then((d) => {
      setForm(d);
      setEdited(null);
    }).catch(() => undefined);
  }, [tkey]);

  const refreshVoices = () => get<Voice[]>("/api/voices").then(setVoices).catch(() => undefined);

  const doPreview = useCallback(async (opts?: { newSeed?: boolean; llm?: boolean }) => {
    if (!template) return;
    const s = opts?.newSeed ? null : seed;
    try {
      const p = await post<Preview>("/api/script/preview", {
        template: tkey, form, patient, datetime: when, style, seed: s, llm_polish: opts?.llm ?? false,
      });
      setPreview(p);
      setSeed(p.seed);
      setEdited(null);
      setErr("");
    } catch (e) {
      setErr(String(e));
    }
  }, [template, tkey, form, patient, when, style, seed]);

  // auto preview on changes (debounced), keeping the seed so edits are stable
  useEffect(() => {
    if (!template) return;
    if (debounce.current) window.clearTimeout(debounce.current);
    debounce.current = window.setTimeout(() => doPreview(), 250);
    return () => {
      if (debounce.current) window.clearTimeout(debounce.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form, patient, when, style, tkey, template]);

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
      });
      setJobId(job.id);
    } catch (e) {
      setErr(String(e));
    }
  };

  const selectedEngineClones = settings ? settings.tts_engine !== "silent" && settings.tts_engine !== "system" : true;
  const doneItem = result?.items[0];
  const wavRel = doneItem?.files?.wav ? doneItem.files.wav.split(/[\\/]/).slice(-1)[0] : "";

  return (
    <div className="cols">
      <div>
        <div className="panel">
          <h2>기록 종류</h2>
          <div className="checks">
            {templates.map((t) => (
              <label key={t.key}>
                <input type="radio" name="tpl" checked={tkey === t.key} onChange={() => setTkey(t.key)} /> {t.title}
              </label>
            ))}
          </div>
          {template && <div className="muted" style={{ marginTop: 6 }}>{template.description} · 시그널 기록종류: <b>{template.signal_kind}</b></div>}
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
                <option value="mixed">현장 혼합 (기본)</option>
                <option value="casual">구어체 위주 (~하시구요)</option>
                <option value="formal">격식체 위주 (~하였습니다)</option>
              </select>
            </div>
          </div>
        </div>

        <PatientPanel patient={patient} onChange={setPatient} onRandom={randomize} />

        <div className="panel">
          <h2>환자 상태 체크 <span className="hint">체크/선택한 항목만 발화됩니다</span></h2>
          {template?.sections.map((s) => (
            <div className="section" key={s.key}>
              <div className="section-head" onClick={() => setCollapsed((c) => ({ ...c, [s.key]: !c[s.key] }))}>
                <strong>{collapsed[s.key] ? "▸" : "▾"} {s.title}<span className="hint">{s.hint}</span></strong>
              </div>
              {!collapsed[s.key] && (
                <div className={s.fields.length > 3 ? "grid2" : ""}>
                  {s.fields.map((f) => (
                    <FieldInput key={f.key} field={f} value={form[f.key]} onChange={(v) => setForm((prev) => ({ ...prev, [f.key]: v }))} />
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      <div>
        <div className="panel">
          <h2>
            발화 대본 미리보기
            <span className="hint">같은 체크 상태에서도 매번 다른 말투로 생성됩니다</span>
            <span style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
              <button className="small" onClick={() => doPreview({ newSeed: true })}>🔀 다른 말투로</button>
              <button className="small" disabled={!settings || settings.llm_provider === "none"} title={settings?.llm_provider === "none" ? "설정에서 LLM API 키를 등록하세요" : ""} onClick={() => doPreview({ llm: true })}>✨ LLM으로 다듬기</button>
              <button className="small" onClick={() => setShowTts((v) => !v)}>{showTts ? "정답 텍스트" : "TTS 발음 텍스트"}</button>
            </span>
          </h2>
          {preview ? (
            showTts ? (
              <div className="preview"><span className="signal">{preview.tts_text.split("\n")[0]}</span>{"\n" + preview.tts_text.split("\n").slice(1).join("\n")}</div>
            ) : (
              <textarea
                className="preview"
                rows={14}
                value={edited ?? preview.spoken_text}
                onChange={(e) => setEdited(e.target.value)}
                spellCheck={false}
              />
            )
          ) : (
            <div className="preview muted">대본이 여기에 표시됩니다…</div>
          )}
          <div className="muted" style={{ marginTop: 6 }}>
            {edited !== null ? <span className="badge warn">직접 수정됨 — 수정한 텍스트가 그대로 녹음·저장됩니다</span> : preview?.llm_polished ? <span className="badge">LLM 다듬기 적용됨</span> : "대본을 직접 고쳐도 됩니다 (첫 줄 시그널은 형식을 유지하세요)."}
            {preview && <> · 파일명: <b>{preview.filename}.wav</b> / .txt / .json</>}
          </div>
        </div>

        <NoisePanel
          value={noise}
          onChange={setNoise}
          extra={
            <label title="등록된 다른 목소리로 회진 대화를 합성해 멀리서 들리게 섞습니다 (목소리 2개 이상 필요)">
              <input type="checkbox" checked={rounds} onChange={(e) => setRounds(e.target.checked)} /> 다른 환자 회진 음성 (TTS)
            </label>
          }
        />

        <div className="panel highlight">
          <h2>녹음 생성</h2>
          <div className="row">
            <div>
              <label>목소리 (등록된 간호사)</label>
              <select value={voiceId} onChange={(e) => setVoiceId(e.target.value)} onFocus={refreshVoices}>
                <option value="">— 선택 —</option>
                {voices.map((v) => (
                  <option key={v.id} value={v.id} disabled={!v.samples.length}>{v.name} ({v.samples.length}개 샘플)</option>
                ))}
              </select>
            </div>
            <div className="narrow">
              <label>
                <input type="checkbox" checked={llm} disabled={!settings || settings.llm_provider === "none" || edited !== null} onChange={(e) => setLlm(e.target.checked)} /> 생성 시 LLM 다듬기
              </label>
            </div>
            <div className="narrow">
              <button className="primary" onClick={generate} disabled={!preview || (selectedEngineClones && !voiceId)}>🎙 발화 + 녹음 저장</button>
            </div>
          </div>
          {!voices.length && <div className="muted">등록된 목소리가 없습니다. "목소리 등록" 탭에서 먼저 녹음하세요. (테스트는 설정에서 시스템/무음 엔진 선택)</div>}
          {err && <div className="error">{err}</div>}
          <JobProgress jobId={jobId} onDone={(j) => { setResult(j); }} />
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
