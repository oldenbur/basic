import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { AlbumEvent, AlbumRef, api, DatedEvent, FaceGroup, FaceGroups, PlacedEvent, PlacementYear, RefExample, RefKind, usd } from "../api";

const REASON_TEXT: Record<string, string> = {
  colour: "colours change", "print size": "print size changes", "new page": "new page",
  "long run": "long run split", "same people (against)": "same people continue",
};
const KIND_TEXT: Record<RefKind, string> = {
  home: "Home", family: "Family home", school: "School", event: "Occasion", trip: "Trip", other: "Other",
};
const printName = (n: string) => n.replace(/^scan/i, "").replace(/\.jpe?g$/i, "");

type Picked = { id: number; name: string; thumb_url: string | null };

// ---------------------------------------------------------------- Events

function EventBlock({ e, picked, onPick }: { e: AlbumEvent; picked: number | null; onPick: (p: Picked) => void }) {
  return (
    <section className="album-event">
      <header>
        <strong>#{e.seq}</strong>
        <span>{e.size} print{e.size === 1 ? "" : "s"} · {printName(e.first_name)}{e.size > 1 && <> – {printName(e.last_name)}</>}</span>
        {e.break_score != null && (
          <span className="muted small" title="How strongly this looks like the start of a new event">
            starts here: {e.break_reasons.map((r) => REASON_TEXT[r] ?? r).join(", ") || "weak signals"} ({e.break_score.toFixed(1)})
          </span>
        )}
        {e.has_me && <span className="me">you're in it</span>}
        {e.people.length > 0 && (
          <span className="small">{e.people.map((p) => `${p.name.split(" ")[0]} ×${p.count}`).join(", ")}</span>
        )}
      </header>
      <div className="strip">
        {e.photos.map((p) => p.thumb_url
          ? <img key={p.id} src={p.thumb_url} loading="lazy" alt={p.name} className={picked === p.id ? "picked" : ""}
              title={`${p.name}${p.faces ? ` · ${p.faces} face${p.faces > 1 ? "s" : ""}` : ""} — click to use as a reference example`}
              onClick={() => onPick(p)} />
          : <span key={p.id} className="muted small">{p.name}</span>)}
      </div>
    </section>
  );
}

function PickBar({ picked, onDone }: { picked: Picked; onDone: () => void }) {
  const qc = useQueryClient();
  const refs = useQuery({ queryKey: ["album-refs"], queryFn: api.albumRefs });
  const [refId, setRefId] = useState<number | "">("");
  const add = useMutation({
    mutationFn: () => api.setExample(Number(refId), picked.id, "confirmed"),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["album-refs"] }); onDone(); },
  });
  return (
    <div className="pick-bar">
      {picked.thumb_url && <img src={picked.thumb_url} alt="" />}
      <span>{printName(picked.name)} shows</span>
      <select value={refId} onChange={(e) => setRefId(e.target.value ? Number(e.target.value) : "")}>
        <option value="">choose a reference…</option>
        {refs.data?.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
      </select>
      <button className="primary" disabled={refId === "" || add.isPending} onClick={() => add.mutate()}>Add as example</button>
      <button className="link" onClick={onDone}>Cancel</button>
      {add.error && <span className="error small">{add.error.message}</span>}
    </div>
  );
}

function EventsTab() {
  const [params, setParams] = useSearchParams();
  const album = params.get("album") ?? undefined;
  const [onlyMe, setOnlyMe] = useState(false);
  const [picked, setPicked] = useState<Picked | null>(null);
  const q = useQuery({ queryKey: ["albums", album], queryFn: () => api.albums(album) });
  if (q.isLoading) return <p className="muted">Loading…</p>;
  if (q.error || !q.data) return <p className="error">{String(q.error)}</p>;
  const d = q.data;
  const current = d.albums.find((a) => a.album === d.album);
  const events = onlyMe ? d.events.filter((e) => e.has_me) : d.events;
  return (
    <>
      <div className="row">
        <div className="chips">
          {d.albums.map((a) => (
            <button key={a.album} className={`chip${a.album === d.album ? " on" : ""}`}
              onClick={() => setParams({ tab: "events", album: a.album })}>
              {a.album} <span className="muted">{a.events} events</span>
            </button>
          ))}
        </div>
        <label className="row small"><input type="checkbox" checked={onlyMe} onChange={(e) => setOnlyMe(e.target.checked)} /> Only events you're in</label>
      </div>
      {current && (
        <p className="muted small">
          {current.prints.toLocaleString()} prints · {current.events} events · {current.events_with_me} with you ·
          click a print to add it as an example of a house, trip or occasion
        </p>
      )}
      {picked && <PickBar picked={picked} onDone={() => setPicked(null)} />}
      {events.map((e) => <EventBlock key={e.id} e={e} picked={picked?.id ?? null} onPick={setPicked} />)}
    </>
  );
}

// ---------------------------------------------------------------- References

function Example({ refId, x }: { refId: number; x: RefExample }) {
  const qc = useQueryClient();
  const done = () => qc.invalidateQueries({ queryKey: ["album-refs"] });
  const set = useMutation({ mutationFn: (s: RefExample["status"]) => api.setExample(refId, x.photo_id, s), onSuccess: done });
  const remove = useMutation({ mutationFn: () => api.removeExample(refId, x.photo_id), onSuccess: done });
  return (
    <div className={`ref-example ${x.status}`}>
      {x.thumb_url ? <img src={x.thumb_url} alt={x.name} loading="lazy" /> : <span>{x.name}</span>}
      <span className="muted">{x.album} {printName(x.name)}{x.status === "proposed" && " · my guess"}</span>
      <div className="row">
        {x.status !== "confirmed" && <button className="small" onClick={() => set.mutate("confirmed")}>✓ Yes</button>}
        {x.status !== "rejected" && <button className="small" onClick={() => set.mutate("rejected")}>✗ No</button>}
        {x.status !== "proposed" && <button className="link small" onClick={() => remove.mutate()}>remove</button>}
      </div>
    </div>
  );
}

function RefCard({ r }: { r: AlbumRef }) {
  const qc = useQueryClient();
  const [start, setStart] = useState(r.start?.slice(0, 7) ?? "");
  const [end, setEnd] = useState(r.end?.slice(0, 7) ?? "");
  const [notes, setNotes] = useState(r.notes ?? "");
  const save = useMutation({
    mutationFn: () => api.editRef(r.id, {
      start: start ? `${start}-01` : null, end: end ? `${end}-01` : null, notes: notes.trim() || null,
    }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["album-refs"] }),
  });
  const del = useMutation({ mutationFn: () => api.deleteRef(r.id), onSuccess: () => qc.invalidateQueries({ queryKey: ["album-refs"] }) });
  const dirty = start !== (r.start?.slice(0, 7) ?? "") || end !== (r.end?.slice(0, 7) ?? "") || notes !== (r.notes ?? "");
  const confirmed = r.examples.filter((x) => x.status === "confirmed").length;
  const proposed = r.examples.filter((x) => x.status === "proposed").length;
  return (
    <section className="ref-card">
      <div className="row">
        <strong>{r.label}</strong>
        <span className="muted small">{KIND_TEXT[r.kind]} · {confirmed} confirmed{proposed > 0 && <>, {proposed} to check</>}</span>
      </div>
      <form className="row small" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
        <label className="row">From <input type="month" value={start} onChange={(e) => setStart(e.target.value)} /></label>
        <label className="row">to <input type="month" value={end} onChange={(e) => setEnd(e.target.value)} /></label>
        <input placeholder="what to look for (optional)" value={notes} onChange={(e) => setNotes(e.target.value)} style={{ minWidth: "18rem" }} />
        <button type="submit" disabled={!dirty || save.isPending}>Save</button>
        <button type="button" className="link" onClick={() => { if (confirm(`Delete “${r.label}”?`)) del.mutate(); }}>Delete</button>
        {save.error && <span className="error">{save.error.message}</span>}
      </form>
      <div className="examples">
        {r.examples.map((x) => <Example key={x.photo_id} refId={r.id} x={x} />)}
        {r.examples.length === 0 && <span className="muted small">No examples yet: find one on the Events tab and click it.</span>}
      </div>
    </section>
  );
}

function NewRef() {
  const qc = useQueryClient();
  const [kind, setKind] = useState<RefKind>("home");
  const [label, setLabel] = useState("");
  const add = useMutation({
    mutationFn: () => api.createRef({ kind, label }),
    onSuccess: () => { setLabel(""); qc.invalidateQueries({ queryKey: ["album-refs"] }); },
  });
  return (
    <form className="row" onSubmit={(e) => { e.preventDefault(); add.mutate(); }}>
      <select value={kind} onChange={(e) => setKind(e.target.value as RefKind)}>
        {Object.entries(KIND_TEXT).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
      </select>
      <input placeholder="e.g. St Pius X school, Feeley cabin" value={label} onChange={(e) => setLabel(e.target.value)} />
      <button type="submit" disabled={!label.trim() || add.isPending}>Add reference</button>
      {add.error && <span className="error small">{add.error.message}</span>}
    </form>
  );
}

function RefsTab() {
  const q = useQuery({ queryKey: ["album-refs"], queryFn: api.albumRefs });
  if (q.isLoading) return <p className="muted">Loading…</p>;
  if (q.error || !q.data) return <p className="error">{String(q.error)}</p>;
  const toCheck = q.data.reduce((n, r) => n + r.examples.filter((x) => x.status === "proposed").length, 0);
  return (
    <>
      <p className="muted">
        Houses, family homes, schools, trips and occasions that pin a print to a period. Confirmed examples are shown to
        the dating model as reference images. Dashed ones are my guesses from looking at the albums
        {toCheck > 0 && <> ({toCheck} to check)</>}: mark each yes or no. A couple of clear examples per reference is plenty.
      </p>
      <NewRef />
      {q.data.map((r) => <RefCard key={`${r.id}-${r.start}-${r.end}-${r.notes}`} r={r} />)}
    </>
  );
}

// ---------------------------------------------------------------- Faces

function GroupBlock({ g, data }: { g: FaceGroup; data: FaceGroups }) {
  const qc = useQueryClient();
  const [out, setOut] = useState<Set<number>>(new Set());
  const [who, setWho] = useState("");
  const [showAll, setShowAll] = useState(false);
  const all = useQuery({ queryKey: ["album-face-group", g.id], queryFn: () => api.faceGroupFaces(g.id), enabled: showAll });
  const faces = showAll && all.data ? all.data : g.faces;
  const done = () => { qc.invalidateQueries({ queryKey: ["album-face-groups"] }); qc.invalidateQueries({ queryKey: ["albums"] }); };
  const name = useMutation({
    // A name you've used before goes to that person (any capitalisation); a new one adds a person.
    mutationFn: () => api.nameFaceGroup(g.id, { name: who.trim() }, [...out]),
    onSuccess: done,
  });
  const ignore = useMutation({ mutationFn: () => api.ignoreFaceGroup(g.id, [...out]), onSuccess: done });
  const toggle = (id: number) => setOut((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  return (
    <section className="face-group">
      <div className="row">
        <strong>{g.size} faces</strong>
        <span className="muted small">{g.first}{g.first !== g.last && <> to {g.last}</>}</span>
        {g.guess_name && <span className="small">closest named person: {g.guess_name} ({g.guess_count} of them)</span>}
      </div>
      <div className="faces">
        {faces.map((f) => f.crop_url && (
          <img key={f.id} src={f.crop_url} alt="" className={out.has(f.id) ? "out" : ""} loading="lazy"
            title={`${f.where}${out.has(f.id) ? " — left out" : " — click to leave this one out"}`} onClick={() => toggle(f.id)} />
        ))}
        {g.size > faces.length && (
          <button type="button" className="link small" onClick={() => setShowAll(true)} disabled={all.isFetching}>
            {all.isFetching ? "Loading…" : `Show all ${g.size}`}
          </button>
        )}
      </div>
      <form className="row" onSubmit={(e) => { e.preventDefault(); name.mutate(); }}>
        <input list="album-people" placeholder="Who is this? Type any name" value={who} onChange={(e) => setWho(e.target.value)}
          style={{ minWidth: "16rem" }} />
        {g.guess_name && !who && (
          <button type="button" className="link small" onClick={() => setWho(g.guess_name ?? "")}>{g.guess_name}?</button>
        )}
        {who.trim() && !data.people.some((p) => p.name.toLowerCase() === who.trim().toLowerCase()) && (
          <span className="muted small">new person</span>
        )}
        <button type="submit" className="primary" disabled={!who.trim() || name.isPending}>
          Name {out.size ? `${g.size - out.size} of them` : "them"}
        </button>
        <button type="button" onClick={() => ignore.mutate()} disabled={ignore.isPending}>Not anyone to name</button>
        {(name.error || ignore.error) && <span className="error small">{(name.error ?? ignore.error)?.message}</span>}
      </form>
    </section>
  );
}

function FacesTab() {
  const qc = useQueryClient();
  const [offset, setOffset] = useState(0);
  const q = useQuery({ queryKey: ["album-face-groups", offset], queryFn: () => api.faceGroups(offset) });
  const regroup = useMutation({
    mutationFn: api.regroupAlbumFaces,
    onSuccess: () => { setOffset(0); qc.invalidateQueries({ queryKey: ["album-face-groups"] }); },
  });
  if (q.isLoading) return <p className="muted">Loading…</p>;
  if (q.error || !q.data) return <p className="error">{String(q.error)}</p>;
  const d = q.data;
  return (
    <>
      <p className="muted">
        Faces in the albums, grouped by likeness. Naming a few groups of you, Rico, Angela, Joe and Martha as children
        lets the rest be recognised, and ages help date the prints. Click a face to leave it out of the group before
        naming. These names stay with the albums; they don't change your People pages.
      </p>
      <div className="row">
        <span className="small">
          {d.named.length > 0 ? <>Named so far: {d.named.map((n) => `${n.name.split(" ")[0]} ${n.count}`).join(", ")}</> : "Nothing named yet."}
        </span>
        <button onClick={() => regroup.mutate()} disabled={regroup.isPending}
          title="Match all faces again using the ones you named, then regroup the rest">
          {regroup.isPending ? "Regrouping…" : "Match & regroup"}
        </button>
      </div>
      <datalist id="album-people">{d.people.map((p) => <option key={p.id} value={p.name} />)}</datalist>
      {d.groups.map((g) => <GroupBlock key={g.id} g={g} data={d} />)}
      {d.total === 0 && <p className="muted">No unnamed groups left.</p>}
      <div className="row">
        <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 10))}>← Bigger groups</button>
        <span className="muted small">{d.total ? `${offset + 1}–${Math.min(offset + 10, d.total)} of ${d.total} groups` : ""}</span>
        <button disabled={offset + 10 >= d.total} onClick={() => setOffset(offset + 10)}>Smaller groups →</button>
      </div>
    </>
  );
}

// ---------------------------------------------------------------- Dating

const range = (lo?: string | null, hi?: string | null) => (lo && hi && lo !== hi ? `${lo} – ${hi}` : lo || hi || "");

function DatedEventBlock({ e }: { e: DatedEvent }) {
  return (
    <section className="dated-event">
      <div className="row">
        <strong>{e.album} #{e.seq}</strong>
        {e.status === "done" ? (
          <>
            <span><strong>{e.best}</strong> <span className="muted small">({range(e.earliest, e.latest)})</span></span>
            <span className={`small conf-${e.confidence}`}>{e.confidence} confidence</span>
            <span>{e.summary}</span>
          </>
        ) : <span className="error small">{e.status}: {e.error}</span>}
      </div>
      {e.clues && <p className="muted small">{e.clues}</p>}
      <div className="prints">
        {e.prints.map((p) => (
          <div key={p.photo_id} className={`dated-print${p.different_occasion ? " odd" : ""}`}
            title={p.different_occasion ? "Looks like a different occasion from the rest" : undefined}>
            {p.thumb_url && <img src={p.thumb_url} alt={p.name} loading="lazy" />}
            <span><strong>{p.best ?? "—"}</strong> <span className={`conf-${p.confidence}`}>{p.confidence}</span></span>
            {range(p.earliest, p.latest) && <span className="muted">{range(p.earliest, p.latest)}</span>}
            {p.ages && p.ages.length > 0 && <span>{p.ages.map((a) => `${a.name} ${a.age}`).join(", ")}</span>}
            {p.reference && <span className="me">{p.reference}</span>}
            {p.caption && <span className="muted">{p.caption}</span>}
          </div>
        ))}
      </div>
    </section>
  );
}

function DatingTab() {
  const qc = useQueryClient();
  const status = useQuery({
    queryKey: ["album-dating"], queryFn: api.dating,
    refetchInterval: (q) => (q.state.data?.runs.some((r) => r.status === "submitted" || r.status === "collecting") ? 30_000 : false),
  });
  const hasPilot = !!status.data?.runs.some((r) => r.kind === "pilot" && r.status !== "failed");
  const estimate = useQuery({ queryKey: ["album-dating-estimate", "pilot"], queryFn: () => api.datingEstimate("pilot"),
    enabled: !!status.data && !hasPilot, staleTime: 10 * 60_000 });
  const results = useQuery({ queryKey: ["album-dating-results", status.data?.dated], queryFn: api.datingResults, enabled: hasPilot });
  const refresh = () => { qc.invalidateQueries({ queryKey: ["album-dating"] }); qc.invalidateQueries({ queryKey: ["album-dating-results"] }); };
  const start = useMutation({ mutationFn: () => api.startDatingPilot(status.data!.pilot_max_usd), onSuccess: refresh });
  const poll = useMutation({ mutationFn: api.pollDating, onSuccess: refresh });
  if (status.isLoading) return <p className="muted">Loading…</p>;
  if (status.error || !status.data) return <p className="error">{String(status.error)}</p>;
  const s = status.data;
  const running = s.runs.some((r) => r.status === "submitted" || r.status === "collecting");
  return (
    <>
      <p className="muted">
        Claude estimates a month for every print from the children's ages, the reference houses, trips and occasions,
        seasons and clothing. These are raw estimates; smoothing them along album order and anchoring them on the
        timeline comes next. {s.dated.toLocaleString()} of {s.prints.toLocaleString()} prints have an estimate.
      </p>
      {!s.has_key && <p className="error">Set ANTHROPIC_API_KEY in backend/.env first.</p>}
      {!hasPilot && (
        <div className="row">
          <button className="primary" disabled={start.isPending || !estimate.data || !s.has_key} onClick={() => start.mutate()}>
            {start.isPending ? "Preparing and sending…" : estimate.data
              ? `Start pilot: ${estimate.data.events} events, ${estimate.data.prints} prints (about ${usd(estimate.data.low)}–${usd(estimate.data.high)})`
              : "Estimating…"}
          </button>
          {start.error && <span className="error small">{start.error.message}</span>}
        </div>
      )}
      {s.runs.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Sent</th><th>Kind</th><th>Status</th><th className="num">Events</th><th className="num">OK</th>
              <th className="num">Failed</th><th className="num">Cost</th></tr></thead>
            <tbody>
              {s.runs.map((r) => (
                <tr key={r.id}>
                  <td>{r.created_at ? new Date(r.created_at + "Z").toLocaleString() : ""}</td>
                  <td>{r.kind}</td><td>{r.status === "submitted" ? "running" : r.status}</td>
                  <td className="num">{r.requests}</td>
                  <td className="num">{r.status === "ended" ? r.succeeded : ""}</td>
                  <td className="num">{r.status === "ended" ? r.errored : ""}</td>
                  <td className="num">{r.cost_usd != null ? usd(r.cost_usd) : <span className="muted">≤{usd(r.est_cost_usd)}</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {running && (
        <div className="row">
          <span className="muted small">Answers usually come back within the hour; this page checks every 30 seconds.</span>
          <button className="link" onClick={() => poll.mutate()} disabled={poll.isPending}>Check now</button>
        </div>
      )}
      {results.data?.map((e) => <DatedEventBlock key={e.id} e={e} />)}
    </>
  );
}

// ---------------------------------------------------------------- Placement

function PlacedEventBlock({ e, onChanged }: { e: PlacedEvent; onChanged: () => void }) {
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const [month, setMonth] = useState(e.your_month ?? "");
  const done = () => { setPicked(new Set()); onChanged(); };
  const move = useMutation({ mutationFn: (to: string) => api.movePrints([...picked], to), onSuccess: done });
  const edit = useMutation({ mutationFn: (x: { status?: "include" | "skip" | "auto"; month?: string }) => api.editEvent(e.key, x), onSuccess: onChanged });
  const busy = move.isPending || edit.isPending;
  const toggle = (id: number) => setPicked((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const span = e.first === e.last ? e.first : `${e.first} – ${e.last}`;
  const decision = e.decision === "include" ? "included (your decision)" : e.decision === "skip" ? "left out (your decision)"
    : e.decision === "undecided" ? "waiting for your decision" : null;
  return (
    <section className="dated-event">
      <div className="row">
        <strong>{e.label}</strong>
        <span><strong>{span}</strong></span>
        {e.has_me && <span className="me small">you're in it</span>}
        <span>{e.summary}</span>
        {decision && <span className={`small ${e.decision === "undecided" ? "muted" : "me"}`}>{decision}</span>}
      </div>
      <div className="row small">
        <button disabled={busy || e.decision === "include"} onClick={() => edit.mutate({ status: "include" })}>Include</button>
        <button disabled={busy || e.decision === "skip"} onClick={() => edit.mutate({ status: "skip" })}>Leave out</button>
        {(e.decision === "include" || e.decision === "skip") &&
          <button className="link" disabled={busy} onClick={() => edit.mutate({ status: "auto" })}>Undo decision</button>}
        <label>Month <input type="month" value={month} onChange={(ev) => setMonth(ev.target.value)} /></label>
        <button disabled={busy || !month || month === e.your_month} onClick={() => edit.mutate({ month })}>Set month</button>
        {e.your_month && <button className="link" disabled={busy} onClick={() => { setMonth(""); edit.mutate({ month: "auto" }); }}>Use estimated month</button>}
        {edit.error && <span className="error">{edit.error.message}</span>}
      </div>
      {picked.size > 0 && (
        <div className="pick-bar">
          <span>{picked.size} selected</span>
          <button className="primary" disabled={busy || picked.size === e.prints.length} onClick={() => move.mutate("new")}>Split into a new event</button>
          {e.prev && <button disabled={busy} onClick={() => move.mutate(e.prev!)}>Move to the event before</button>}
          {e.next && <button disabled={busy} onClick={() => move.mutate(e.next!)}>Move to the event after</button>}
          <button className="link" onClick={() => setPicked(new Set())}>Clear</button>
          {move.error && <span className="error small">{move.error.message}</span>}
        </div>
      )}
      <div className="prints">
        {e.prints.map((p) => (
          <div key={p.photo_id} className={`dated-print pickable${picked.has(p.photo_id) ? " picked" : ""}`}
            onClick={() => toggle(p.photo_id)} title="Click to select">
            {p.thumb_url && <img src={p.thumb_url} alt={p.name} loading="lazy" />}
            <span><strong>{p.month}</strong> <span className="muted">{p.name}</span></span>
            {p.status !== "include" && <span className="muted">{p.status === "older" ? "older, kept out" : p.status === "skip" ? "left out" : "waiting"}</span>}
          </div>
        ))}
      </div>
    </section>
  );
}

function PlacementTab() {
  const qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const view = params.get("view") === "all" ? "all" : "review";
  const year = params.get("year") ? Number(params.get("year")) : undefined;
  const set = (k: string, v: string | null) => { const n = new URLSearchParams(params); if (v) n.set(k, v); else n.delete(k); setParams(n, { replace: true }); };
  const q = useQuery({ queryKey: ["album-placements", view, year], queryFn: () => api.placements(view, year), placeholderData: (d) => d });
  const refresh = () => qc.invalidateQueries({ queryKey: ["album-placements"] });
  const rerun = useMutation({ mutationFn: api.runPlacement, onSuccess: refresh });
  if (q.isLoading) return <p className="muted">Loading…</p>;
  if (q.error || !q.data) return <p className="error">{String(q.error)}</p>;
  const { years, events } = q.data;
  const total = (k: keyof PlacementYear) => years.reduce((n, y) => n + ((y[k] as number) || 0), 0);
  return (
    <>
      <p className="muted">
        Each print's settled month and the year folder it would be copied into. Nothing is copied yet. Prints before
        1972 stay out for now; from 1995 on, only events you're recognised in are included unless you decide otherwise.
        Click prints to select them, then split them into a new event or move them to the event before or after.
        Your splits, months and decisions are kept when months are recomputed.
      </p>
      <div className="row">
        <span>{total("include").toLocaleString()} to copy · {total("older")} older · {total("review")} waiting · {total("skip")} left out</span>
        <button className="link" onClick={() => rerun.mutate()} disabled={rerun.isPending}>
          {rerun.isPending ? "Recomputing…" : "Recompute months"}</button>
      </div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Year</th><th className="num">To copy</th><th className="num">Waiting</th>
            <th className="num">Left out</th><th className="num">Older</th></tr></thead>
          <tbody>
            {years.map((y) => (
              <tr key={y.year} className={y.year === year ? "selected" : undefined}>
                <td><button className="link" onClick={() => { set("year", y.year === year ? null : String(y.year)); }}>{y.year}</button></td>
                <td className="num">{y.include ?? ""}</td><td className="num">{y.review ?? ""}</td>
                <td className="num">{y.skip ?? ""}</td><td className="num">{y.older ?? ""}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="row">
        <div className="tabs">
          <button className={view === "review" ? "active" : ""} onClick={() => set("view", null)}>From 1995 on, without you</button>
          <button className={view === "all" ? "active" : ""} onClick={() => set("view", "all")}>All events</button>
        </div>
        {year && <span>in {year} <button className="link" onClick={() => set("year", null)}>any year</button></span>}
        <span className="muted small">{events.length} events{view === "review" ? `, ${events.filter((e) => e.decision === "undecided").length} undecided` : ""}</span>
      </div>
      {view === "all" && !year && events.length > 60 && <p className="muted small">Showing every event; pick a year above to narrow it.</p>}
      {events.map((e) => <PlacedEventBlock key={`${e.key}-${e.prints.length}-${e.your_month}`} e={e} onChanged={refresh} />)}
    </>
  );
}

// ---------------------------------------------------------------- Page

const TABS = { events: "Events", refs: "References", faces: "Faces", dating: "Dating", placement: "Placement" } as const;
type Tab = keyof typeof TABS;

export function Albums() {
  const [params, setParams] = useSearchParams();
  const tab = (params.get("tab") as Tab) in TABS ? (params.get("tab") as Tab) : "events";
  return (
    <>
      <div className="folder-header">
        <div>
          <h1>Old albums</h1>
          <p className="muted">
            The scanned print albums, split into events: runs of prints from one roll or occasion. Nothing here is in
            your library yet; these events are what will be dated and copied into year folders.
          </p>
        </div>
      </div>
      <div className="tabs">
        {(Object.keys(TABS) as Tab[]).map((t) => (
          <button key={t} className={t === tab ? "on" : ""} onClick={() => setParams({ tab: t })}>{TABS[t]}</button>
        ))}
      </div>
      {tab === "events" && <EventsTab />}
      {tab === "refs" && <RefsTab />}
      {tab === "faces" && <FacesTab />}
      {tab === "dating" && <DatingTab />}
      {tab === "placement" && <PlacementTab />}
    </>
  );
}
