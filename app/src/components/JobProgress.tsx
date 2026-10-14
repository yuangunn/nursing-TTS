import { useEffect, useState } from "react";
import { get, Job } from "../lib/api";

interface Props {
  jobId: string | null;
  onDone?: (job: Job) => void;
}

export default function JobProgress({ jobId, onDone }: Props) {
  const [job, setJob] = useState<Job | null>(null);
  useEffect(() => {
    if (!jobId) {
      setJob(null);
      return;
    }
    let alive = true;
    const tick = async () => {
      try {
        const j = await get<Job>(`/api/jobs/${jobId}`);
        if (!alive) return;
        setJob(j);
        if (["done", "error", "cancelled"].includes(j.status)) {
          onDone?.(j);
          return;
        }
      } catch {
        /* ignore */
      }
      if (alive) setTimeout(tick, 700);
    };
    tick();
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);
  if (!job) return null;
  const pct = job.total ? Math.round((job.done / job.total) * 100) : 0;
  return (
    <div>
      <div className="progress"><div style={{ width: `${pct}%` }} /></div>
      <div className="muted">
        {job.status === "running" && "⏳ "}
        {job.status === "done" && "✅ "}
        {job.status === "error" && "❌ "}
        {job.message || job.status} {job.total > 1 && `(${job.done}/${job.total})`}
      </div>
      {job.error && <div className="error">{job.error}</div>}
    </div>
  );
}
