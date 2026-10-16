import { useEffect, useState } from "react";
import JobProgress from "../components/JobProgress";
import AugmentPanel from "../components/AugmentPanel";
import NoisePanel from "../components/NoisePanel";
import SignalSelect from "../components/SignalSelect";
import { playVoiceDemo } from "../lib/voiceDemo";
import { AugmentSettings, DEFAULT_AUGMENT, DEFAULT_NOISE, get, Job, NoiseSettings, post, Settings, TemplateSchema, Voice } from "../lib/api";

export default function BatchPage() {
  const [templates, setTemplates] = useState<TemplateSchema[]>([]);
  const [voices, setVoices] = useState<Voice[]>([]);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [count, setCount] = useState(20);
  const [sel, setSel] = useState<string[]>(["s1", "s2", "s3_1", "s3_2", "s4", "s5"]);
  const [voiceIds, setVoiceIds] = useState<string[]>([]);
  const [demoBusy, setDemoBusy] = useState("");
  const [demoError, setDemoError] = useState("");
  const [noise, setNoise] = useState<NoiseSettings>({ ...DEFAULT_NOISE, enabled: true });
  const [noiseProb, setNoiseProb] = useState(0.5);
  const [style, setStyle] = useState("");
  const [llm, setLlm] = useState(false);
  const [rounds, setRounds] = useState(false);
  const [dialogueS1, setDialogueS1] = useState(false);
  const [folder, setFolder] = useState("");
  const [augment, setAugment] = useState<AugmentSettings>({ ...DEFAULT_AUGMENT, enabled: true });
  const [disfluency, setDisfluency] = useState<number | "random">("random");
  const [signalFormat, setSignalFormat] = useState("random");
  const [signalAliases, setSignalAliases] = useState<boolean | null>(true);
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    get<TemplateSchema[]>("/api/templates").then(setTemplates).catch(() => undefined);
    get<Voice[]>("/api/voices").then((vs) => {
      setVoices(vs);
      setVoiceIds(vs.filter((v) => v.samples.length).map((v) => v.id));
    }).catch(() => undefined);
    get<Settings>("/api/settings").then(setSettings).catch(() => undefined);
    get<Job[]>("/api/jobs").then(setJobs).catch(() => undefined);
  }, []);

  const toggle = (arr: string[], v: string, set: (a: string[]) => void) => set(arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]);
  const clones = settings ? !["silent", "system"].includes(settings.tts_engine) : true;

  const start = async () => {
    setErr("");
    setJob(null);
    try {
      const j = await post<Job>("/api/batch", {
        count, templates: sel, voice_ids: voiceIds, noise, noise_prob: noiseProb, style: style || null,
        llm_polish: llm, rounds_voice: rounds, folder_name: folder, augment, disfluency, dialogue_s1: dialogueS1, patient_voice_id: "auto",
        signal_format: signalFormat || "random", signal_aliases: signalAliases,
      });
      setJobId(j.id);
    } catch (e) {
      setErr(String(e));
    }
  };

  const cancel = async () => {
    if (jobId) await post(`/api/jobs/${jobId}/cancel`);
  };

  const refreshJobs = () => get<Job[]>("/api/jobs").then(setJobs).catch(() => undefined);

  return (
    <div className="cols">
      <div>
        <div className="panel">
          <h2>가상 환자 대량 생성 <span className="hint">환자·날짜·상태를 무작위로 만들어 N개의 녹음을 생성합니다</span></h2>
          <div className="row">
            <div className="narrow">
              <label>생성 개수</label>
              <input type="number" min={1} max={2000} value={count} onChange={(e) => setCount(Number(e.target.value))} />
            </div>
            <div>
              <label>말투</label>
              <select value={style} onChange={(e) => setStyle(e.target.value)}>
                <option value="">무작위 섞기 (격식체 위주, 권장)</option>
                <option value="formal">격식체 위주</option>
                <option value="mixed">현장 혼합</option>
                <option value="casual">구어체 위주</option>
                <option value="chart">기록체 (~함/~됨)</option>
              </select>
            </div>
            <div>
              <label>저장 폴더 이름 (출력 폴더 하위)</label>
              <input type="text" value={folder} placeholder="비우면 batch_날짜시각" onChange={(e) => setFolder(e.target.value)} />
            </div>
          </div>
          <div style={{ marginBottom: 10 }}>
            <SignalSelect value={signalFormat} onChange={setSignalFormat} allowDefault={false} aliases={signalAliases} onAliases={setSignalAliases} />
            <div className="example">트리거 검출 모델이 다양한 시작 문장을 배우도록 대량 생성에서는 무작위 혼합을 권장합니다. 내보내기 manifest에 시그널 문장·구간·환자명·시각·기록종류 라벨이 함께 저장됩니다.</div>
          </div>
          <div className="field">
            <label>기록 종류 (무작위로 섞임)</label>
            <div className="checks">
              {templates.map((t) => (
                <label key={t.key}><input type="checkbox" checked={sel.includes(t.key)} onChange={() => toggle(sel, t.key, setSel)} /> {t.title}</label>
              ))}
            </div>
          </div>
          <div className="field">
            <label>목소리 (여러 개 선택 시 무작위 배정)</label>
            <div className="checks">
              {voices.filter((v) => v.samples.length).map((v) => (
                <label key={v.id}><input type="checkbox" checked={voiceIds.includes(v.id)} onChange={() => toggle(voiceIds, v.id, setVoiceIds)} /> {v.name}
                  <button type="button" className="link" title="이 목소리로 고정 문장을 한 번 합성해 들려줍니다" style={{ marginLeft: 4 }} disabled={demoBusy === v.id}
                    onClick={(e) => { e.preventDefault(); playVoiceDemo(v.id, setDemoBusy, setDemoError); }}>{demoBusy === v.id ? "⏳" : "🔊"}</button>
                </label>
              ))}
              {!voices.filter((v) => v.samples.length).length && <span className="muted">샘플이 있는 목소리가 없습니다.</span>}
              {demoError && <span className="muted">{demoError}</span>}
            </div>
          </div>
          <div className="checks">
            <label><input type="checkbox" checked={llm} disabled={!settings || settings.llm_provider === "none"} onChange={(e) => setLlm(e.target.checked)} /> LLM 다듬기 (API 비용 발생)</label>
            <label><input type="checkbox" checked={rounds} onChange={(e) => setRounds(e.target.checked)} /> 일부 녹음에 다른 환자 회진 음성 섞기</label>
            <label title="간호사 질문(~까요?)과 환자 대답(~어요/네/아니오, 80세 이상은 반말)을 환자 성별에 맞는 등록 목소리로 읽습니다"><input type="checkbox" checked={dialogueS1} onChange={(e) => setDialogueS1(e.target.checked)} /> 간호정보조사는 환자 대답 포함(대화형, 두 목소리)</label>
          </div>
        </div>
        <AugmentPanel value={augment} onChange={setAugment} disfluency={disfluency} onDisfluency={setDisfluency} allowRandomDisfluency />
        <NoisePanel
          value={noise}
          onChange={setNoise}
          extra={
            <span className="slider" style={{ minWidth: 260 }}>
              <span className="muted">소음 포함 비율</span>
              <input type="range" min={0} max={1} step={0.05} value={noiseProb} disabled={!noise.enabled} onChange={(e) => setNoiseProb(Number(e.target.value))} />
              <span className="muted">{Math.round(noiseProb * 100)}%</span>
            </span>
          }
        />
      </div>
      <div>
        <div className="panel highlight">
          <h2>실행</h2>
          <div className="row">
            <div className="narrow"><button className="primary" onClick={start} disabled={!sel.length || (clones && !voiceIds.length) || (job?.status === "running")}>🚀 {count}개 생성 시작</button></div>
            <div className="narrow"><button onClick={cancel} disabled={!jobId || !!job}>중단</button></div>
            {job?.folder && <div className="narrow"><button onClick={() => window.nursing?.openPath(job.folder)}>📂 결과 폴더 열기</button></div>}
          </div>
          <div className="muted">파일명: 시그널 발화시각_환자명 (예: 20261018_1110_홍길동.wav + .txt 정답 텍스트 + .json 메타)</div>
          {err && <div className="error">{err}</div>}
          <JobProgress jobId={jobId} onDone={(j) => { setJob(j); refreshJobs(); }} />
          {job && (
            <div className="stat">
              <div><div className="k">완료</div><div className="v">{job.done}/{job.total}</div></div>
              <div><div className="k">오류</div><div className="v">{job.items.filter((i) => i.status === "error").length}</div></div>
              <div><div className="k">총 길이</div><div className="v">{Math.round(job.items.reduce((a, i) => a + (i.duration || 0), 0))}s</div></div>
            </div>
          )}
          {job && (
            <table className="items" style={{ marginTop: 8 }}>
              <thead><tr><th>#</th><th>환자</th><th>종류</th><th>길이</th><th>상태</th></tr></thead>
              <tbody>
                {job.items.map((i) => (
                  <tr key={i.index}>
                    <td>{i.index + 1}</td><td>{i.patient}</td><td>{i.template}</td><td>{i.duration ? `${i.duration}s` : ""}</td>
                    <td>{i.status === "error" ? <span className="badge bad" title={i.error}>오류</span> : i.status === "done" ? <span className="badge ok">완료</span> : i.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        <div className="panel">
          <h2>최근 작업 <button className="small" style={{ marginLeft: "auto" }} onClick={refreshJobs}>새로고침</button></h2>
          <ul className="list">
            {jobs.map((j) => (
              <li key={j.id}>
                <div className="grow">
                  <b>{j.kind === "batch" ? "대량" : "단일"}</b> {j.total}개 · {j.status} <span className="muted">{new Date(j.created * 1000).toLocaleString()}</span>
                  {j.folder && <div className="muted">{j.folder}</div>}
                </div>
                {j.folder && <button className="small" onClick={() => window.nursing?.openPath(j.folder)}>열기</button>}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
