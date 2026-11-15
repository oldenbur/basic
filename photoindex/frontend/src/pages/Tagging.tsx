import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, TaggingStatus, usd } from "../api";

const STATE_TEXT: Record<TaggingStatus["state"], string> = {
  not_started: "Not started. Run the pilot to compare the models on the same photos first.",
  pilot: "Pilot sent. Compare the answers, then choose the model to tag everything with.",
  running: "Tagging highlights in the background.",
  waiting_cap: "Waiting: today's spend cap is used up. Tagging picks up again tomorrow (UTC), or raise the cap.",
  paused: "Paused.",
  done: "Every highlight is tagged.",
};

function CapForm({ cap }: { cap: number }) {
  const qc = useQueryClient();
  const [value, setValue] = useState(String(cap));
  const save = useMutation({
    mutationFn: () => api.taggingSettings({ daily_cap: Number(value) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tagging"] }),
  });
  return (
    <form className="row" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
      <span>Daily cap $</span>
      <input className="narrow" inputMode="decimal" value={value} onChange={(e) => setValue(e.target.value)} />
      <button type="submit" disabled={save.isPending || Number(value) === cap || !(Number(value) >= 0)}>Save</button>
      {save.error && <span className="error small">{save.error.message}</span>}
    </form>
  );
}

export function Tagging() {
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["tagging"], queryFn: api.tagging,
    refetchInterval: (query) => {
      const d = query.state.data;
      return d && (d.pilot_starting || d.runs.some((r) => r.status === "submitted" || r.status === "collecting")) ? 5000 : 30_000;
    },
  });
  const [size, setSize] = useState(300);
  const refresh = () => qc.invalidateQueries({ queryKey: ["tagging"] });
  const pilot = useMutation({ mutationFn: () => api.startPilot(size), onSuccess: refresh });
  const pause = useMutation({ mutationFn: (paused: boolean) => api.taggingSettings({ paused }), onSuccess: refresh });
  const poll = useMutation({ mutationFn: api.pollTagging, onSuccess: () => setTimeout(refresh, 1500) });

  if (q.isLoading) return <p className="muted">Loading…</p>;
  if (q.error || !q.data) return <p className="error">{String(q.error)}</p>;
  const s = q.data;
  const total = Object.values(s.counts).reduce((a, b) => a + b, 0);
  const tagged = s.tagged;
  const chosen = s.models.find((m) => m.id === s.config.model);
  const hasPilot = s.runs.some((r) => r.kind === "pilot");
  const pilotEstimate = s.models.reduce((sum, m) => sum + (m.per_photo ?? m.estimate_all / Math.max(total, 1)) * size, 0);

  return (
    <>
      <div className="folder-header">
        <div>
          <h1>AI tags</h1>
          <p className="muted">{STATE_TEXT[s.state]}</p>
        </div>
        <div className="actions">
          {hasPilot && <Link className="button primary" to="/tagging/compare">Compare models</Link>}
          <Link className="button" to="/tags">Tags</Link>
        </div>
      </div>

      {!s.has_key && <p className="error">Set <code>ANTHROPIC_API_KEY</code> in <code>backend/.env</code> and restart the server.</p>}
      {s.worker_error && <p className="error small">Last background check failed: {s.worker_error}</p>}

      <div className="tag-progress">
        <div>
          <span>
            <strong>{tagged.toLocaleString()}</strong> of {total.toLocaleString()} highlights tagged
            {(s.counts.queued ?? 0) > 0 && <> · {s.counts.queued.toLocaleString()} in batches now</>}
            {(s.counts.error ?? 0) > 0 && <> · <span className="error">{s.counts.error} failed</span></>}
          </span>
          <progress max={total || 1} value={tagged} />
        </div>
        <div>
          <span>Spent today <strong>{usd(s.spent_today)}</strong> of {usd(s.config.daily_cap)} · {usd(s.total_cost)} in all</span>
          <CapForm key={s.config.daily_cap} cap={s.config.daily_cap} />
        </div>
      </div>

      {s.config.model ? (
        <div className="row">
          <span>Model: <strong>{chosen?.label ?? s.config.model}</strong>
            {chosen && s.state !== "done" && <> · about {usd(chosen.estimate_remaining)} to finish{chosen.measured ? "" : " (estimate)"}</>}
          </span>
          <button onClick={() => pause.mutate(!s.config.paused)} disabled={pause.isPending}>{s.config.paused ? "Resume" : "Pause"}</button>
          <button className="link" onClick={() => poll.mutate()} disabled={poll.isPending}
            title="The server checks every minute; this checks now">Check now</button>
        </div>
      ) : !hasPilot ? (
        <section className="panel">
          <h2>Pilot</h2>
          <p>
            Sends the same highlights, spread across the years, to all three models. Answers come back within an hour
            or so (the Batch API allows up to 24). Then you compare them side by side and pick one.
          </p>
          <form className="row" onSubmit={(e) => { e.preventDefault(); pilot.mutate(); }}>
            <label className="row">Photos <select value={size} onChange={(e) => setSize(Number(e.target.value))}>
              {[100, 200, 300].map((n) => <option key={n}>{n}</option>)}
            </select></label>
            <button type="submit" className="primary" disabled={pilot.isPending || s.pilot_starting || !s.has_key}>
              {s.pilot_starting ? "Sending…" : `Start pilot (about ${usd(pilotEstimate)})`}
            </button>
          </form>
          {(pilot.error || s.pilot_error) && <p className="error small">{pilot.error?.message ?? s.pilot_error}</p>}
          <table className="stats">
            <thead><tr><th>Model</th><th className="num">Per photo</th><th className="num">All {total.toLocaleString()} highlights</th></tr></thead>
            <tbody>
              {s.models.map((m) => (
                <tr key={m.id}><td>{m.label}</td><td className="num">{usd(m.per_photo ?? m.estimate_all / Math.max(total, 1), 4)}</td>
                  <td className="num">{usd(m.estimate_all)}</td></tr>
              ))}
            </tbody>
          </table>
          <p className="muted small">Estimates until the pilot measures real token counts. Batch prices (half the list price).</p>
        </section>
      ) : null}

      {s.runs.length > 0 && (
        <>
          <h2>Batches</h2>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Sent</th><th>Kind</th><th>Model</th><th>Status</th><th className="num">Photos</th>
                <th className="num">OK</th><th className="num">Failed</th><th className="num">Cost</th></tr></thead>
              <tbody>
                {s.runs.map((r) => (
                  <tr key={r.id}>
                    <td>{r.created_at ? new Date(r.created_at + "Z").toLocaleString() : ""}</td>
                    <td>{r.kind}</td>
                    <td>{s.models.find((m) => m.id === r.model)?.label ?? r.model}</td>
                    <td>{r.status === "submitted" ? "running" : r.status}</td>
                    <td className="num">{r.requests}</td>
                    <td className="num">{r.status === "ended" ? r.succeeded : ""}</td>
                    <td className="num">{r.status === "ended" ? r.errored : ""}</td>
                    <td className="num">{r.cost_usd != null ? usd(r.cost_usd) : <span className="muted">~{usd(r.est_cost_usd)}</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}
