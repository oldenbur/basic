import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { AlbumEvent, AlbumRef, api, FaceGroup, FaceGroups, RefExample, RefKind } from "../api";

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
  const [who, setWho] = useState<string>(g.guess_id ? String(g.guess_id) : "");
  const [newName, setNewName] = useState("");
  const [showAll, setShowAll] = useState(false);
  const all = useQuery({ queryKey: ["album-face-group", g.id], queryFn: () => api.faceGroupFaces(g.id), enabled: showAll });
  const faces = showAll && all.data ? all.data : g.faces;
  const done = () => { qc.invalidateQueries({ queryKey: ["album-face-groups"] }); qc.invalidateQueries({ queryKey: ["albums"] }); };
  const name = useMutation({
    mutationFn: () => api.nameFaceGroup(g.id, who === "new" ? { name: newName } : { person_id: Number(who) }, [...out]),
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
        <select value={who} onChange={(e) => setWho(e.target.value)}>
          <option value="">Who is this?</option>
          {data.people.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          <option value="new">Someone new…</option>
        </select>
        {who === "new" && <input placeholder="Name" value={newName} onChange={(e) => setNewName(e.target.value)} />}
        <button type="submit" className="primary" disabled={!who || (who === "new" && !newName.trim()) || name.isPending}>
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

// ---------------------------------------------------------------- Page

const TABS = { events: "Events", refs: "References", faces: "Faces" } as const;
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
    </>
  );
}
