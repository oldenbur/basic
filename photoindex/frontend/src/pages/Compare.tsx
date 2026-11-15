import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, CATEGORY_LABEL, PilotAnswer, PilotPhoto, tagLabel, TagCategory, usd } from "../api";

const LETTERS = ["A", "B", "C", "D"];

function Summary({ photos }: { photos: number }) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const pilot = useQuery({ queryKey: ["pilot"], queryFn: api.pilot });
  const status = useQuery({ queryKey: ["tagging"], queryFn: api.tagging });
  const [confirm, setConfirm] = useState<string | null>(null);
  const choose = useMutation({
    mutationFn: (model: string) => api.chooseModel(model),
    onSuccess: () => { qc.invalidateQueries(); navigate("/tagging"); },
  });
  if (!pilot.data) return null;
  const chosen = status.data?.config.model;
  const remaining = (m: string) => status.data?.models.find((x) => x.id === m)?.estimate_remaining;
  return (
    <div className="table-wrap">
      <table className="compare-summary">
        <thead>
          <tr><th>Model</th><th className="num">Answered</th><th className="num">Your pick</th>
            <th className="num">Has wrong tags</th><th className="num">Says rotate</th><th className="num">Per photo</th>
            <th className="num">All {pilot.data.highlights.toLocaleString()} highlights</th><th /></tr>
        </thead>
        <tbody>
          {pilot.data.models.map((m) => (
            <tr key={m.model}>
              <td><strong>{m.label}</strong></td>
              <td className="num">{m.done}/{m.answers}</td>
              <td className="num">{m.best}{pilot.data.voted ? <span className="muted"> ({Math.round((100 * m.best) / pilot.data.voted)}%)</span> : null}</td>
              <td className="num">{m.flagged}{m.flags > m.flagged && <span className="muted"> ({m.flags} tags)</span>}</td>
              <td className="num">{m.rotations}</td>
              <td className="num">{usd(m.per_photo, 4)}</td>
              <td className="num">{usd(m.estimate_all)}</td>
              <td>
                {chosen === m.model ? <span className="muted">in use</span> : confirm === m.model ? (
                  <span className="row">
                    <button className="primary" onClick={() => choose.mutate(m.model)} disabled={choose.isPending}>
                      Tag the rest (~{usd(remaining(m.model))})
                    </button>
                    <button className="link" onClick={() => setConfirm(null)}>Cancel</button>
                  </span>
                ) : (
                  <button onClick={() => setConfirm(m.model)} disabled={pilot.data.running > 0}>Use {m.label}</button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted small">
        {pilot.data.voted} of {photos} photos compared. Choosing a model applies its pilot answers now and sends the
        other highlights in batches, within the daily cap.
        {choose.error && <span className="error"> {choose.error.message}</span>}
      </p>
    </div>
  );
}

function Answer({ a, letter, reveal, flags, best, onFlag, onBest, index }: {
  a: PilotAnswer; letter: string; reveal: boolean; flags: Set<string>; best: boolean; index: number;
  onFlag: (f: string) => void; onBest: () => void;
}) {
  if (a.status !== "done") {
    return <div className="answer"><h3>{letter}{reveal && ` · ${a.label}`}</h3><p className="error small">{a.status}: {a.error}</p></div>;
  }
  const byCat = new Map<string, string[]>();
  for (const t of a.tags) {
    const cat = t.slice(0, t.indexOf(":"));
    byCat.set(cat, [...(byCat.get(cat) ?? []), t]);
  }
  const loc = a.location;
  const place = loc && [loc.place_name, loc.city, loc.region, loc.country].filter(Boolean).join(", ");
  const flagBtn = (key: string, body: React.ReactNode) => (
    <button key={key} className={`flaggable ${flags.has(key) ? "flagged" : ""}`} onClick={() => onFlag(key)}
      title={flags.has(key) ? "Marked wrong. Click to undo." : "Click if this is wrong"}>{body}</button>
  );
  return (
    <div className={`answer ${best ? "best" : ""}`}>
      <div className="answer-head">
        <h3>{letter}{reveal && <span className="muted"> · {a.label}</span>}</h3>
        <button className={best ? "primary" : ""} onClick={onBest}>{best ? "★ Best" : "Best"} <kbd>{index + 1}</kbd></button>
      </div>
      <p>{flagBtn("caption", a.caption)}</p>
      <div className="answer-meta">
        {flagBtn("aesthetic", <>score {a.aesthetic}/10</>)}
        {a.rotation ? flagBtn("rotation", <span className="warn">turn {a.rotation}°</span>) : null}
        {place && flagBtn("location", <>{place} <span className="muted">({loc?.confidence})</span></>)}
        <span className="muted">{a.people_count} people · {a.setting}</span>
      </div>
      {[...byCat.entries()].map(([cat, tags]) => (
        <div key={cat} className="answer-tags">
          <span className="muted small">{CATEGORY_LABEL[cat as TagCategory] ?? cat}</span>
          {tags.map((t) => flagBtn(t, tagLabel(t)))}
        </div>
      ))}
      {reveal && <p className="muted small">{usd(a.cost_usd, 4)} · {a.output_tokens} output tokens</p>}
    </div>
  );
}

function PhotoCompare({ photo, onNext }: { photo: PilotPhoto; onNext: () => void }) {
  const qc = useQueryClient();
  const [best, setBest] = useState<number | null>(() => photo.answers.find((a) => a.best)?.id ?? null);
  const [flags, setFlags] = useState<Record<number, Set<string>>>(() =>
    Object.fromEntries(photo.answers.map((a) => [a.id, new Set(a.flags)])));
  const [reveal, setReveal] = useState(photo.voted);
  const save = useMutation({
    mutationFn: (v: { best: number | null; flags: Record<number, Set<string>> }) =>
      api.vote(photo.photo_id, v.best, Object.fromEntries(Object.entries(v.flags).map(([k, s]) => [k, [...s]]))),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pilot"] }),
  });
  const pick = (id: number | null) => {
    setBest(id);
    setReveal(true);
    save.mutate({ best: id, flags });
  };
  const flag = (id: number, f: string) => {
    const next = { ...flags, [id]: new Set(flags[id]) };
    if (next[id].has(f)) next[id].delete(f); else next[id].add(f);
    setFlags(next);
    save.mutate({ best, flags: next });
  };
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) return;
      const n = Number(e.key);
      if (n >= 1 && n <= photo.answers.length) pick(photo.answers[n - 1].id);
      if (e.key === "0") pick(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });
  return (
    <div className="compare">
      <div className="compare-photo">
        <img src={photo.display_url} alt={photo.name} />
        <p className="muted small">{photo.name}</p>
      </div>
      <div className="answers">
        {photo.answers.map((a, i) => (
          <Answer key={a.id} a={a} letter={LETTERS[i]} index={i} reveal={reveal} best={best === a.id}
            flags={flags[a.id] ?? new Set()} onFlag={(f) => flag(a.id, f)} onBest={() => pick(a.id)} />
        ))}
        <div className="row">
          <button onClick={() => pick(null)}>None stands out <kbd>0</kbd></button>
          {!reveal && <button className="link" onClick={() => setReveal(true)}>Show which model is which</button>}
          <span className="spacer" />
          <button className="primary" onClick={onNext}>Next <kbd>→</kbd></button>
          {save.error && <span className="error small">{save.error.message}</span>}
        </div>
        <p className="muted small">
          Click anything that's wrong (a tag, the caption, the place, a rotation) to mark it. Model names stay hidden
          until you pick, so the vote is blind.
        </p>
      </div>
    </div>
  );
}

export function Compare() {
  const pilot = useQuery({ queryKey: ["pilot"], queryFn: api.pilot, refetchInterval: (q) => (q.state.data?.running ? 10_000 : false) });
  const photos = useMemo(() => pilot.data?.photos ?? [], [pilot.data?.photos]);
  const [index, setIndex] = useState<number | null>(null);
  // Start at the first photo not compared yet; after that, only the buttons and arrow keys move.
  useEffect(() => {
    if (index === null && photos.length) setIndex(Math.max(0, photos.findIndex((p) => !p.voted)));
  }, [index, photos]);
  const i = Math.min(index ?? 0, Math.max(photos.length - 1, 0));
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) return;
      if (e.key === "ArrowRight") setIndex(Math.min(i + 1, photos.length - 1));
      if (e.key === "ArrowLeft") setIndex(Math.max(i - 1, 0));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [i, photos.length]);

  if (pilot.isLoading) return <p className="muted">Loading…</p>;
  if (pilot.error || !pilot.data) return <p className="error">{String(pilot.error)}</p>;
  const current = photos[i];
  return (
    <>
      <div className="crumbs"><Link to="/tagging">AI tags</Link></div>
      <h1>Compare models</h1>
      {pilot.data.runs === 0 ? <p className="muted">No pilot yet. Start one on the <Link to="/tagging">AI tags</Link> page.</p> : (
        <>
          <Summary photos={photos.length} />
          {pilot.data.running > 0 && <p className="muted">{pilot.data.running} of {pilot.data.runs} models still answering…</p>}
          {current && (
            <>
              <div className="row compare-nav">
                <button onClick={() => setIndex(Math.max(i - 1, 0))} disabled={i === 0}>← Prev</button>
                <span>Photo {i + 1} of {photos.length}</span>
                <button className="link" onClick={() => setIndex(Math.max(0, photos.findIndex((p, j) => j > i && !p.voted)))}>Next not compared</button>
              </div>
              <PhotoCompare key={current.photo_id} photo={current} onNext={() => setIndex(Math.min(i + 1, photos.length - 1))} />
            </>
          )}
        </>
      )}
    </>
  );
}
