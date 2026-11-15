import { useInfiniteQuery, useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, queryParams } from "../api";
import { FaceCrop, useFaceRefresh, usePeople } from "../components/People";
import { Lightbox, PhotoTiles } from "../components/Photos";

const PAGE = 200;

export function PersonView() {
  const id = Number(useParams().id);
  const navigate = useNavigate();
  const refresh = useFaceRefresh();
  const people = usePeople();
  const person = useQuery({ queryKey: ["person", id], queryFn: () => api.person(id) });
  const [tab, setTab] = useState<"photos" | "faces">("photos");
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [mergeInto, setMergeInto] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [open, setOpen] = useState<number | null>(null);

  const query = { people: [id] };
  const photos = useInfiniteQuery({
    queryKey: ["search", query, "date", 0],
    queryFn: ({ pageParam }) => api.search(query, { sort: "date", offset: pageParam, limit: PAGE, with_facets: pageParam === 0 }),
    initialPageParam: 0,
    getNextPageParam: (last, pages) => (last.has_more ? pages.length * PAGE : undefined),
    enabled: tab === "photos",
  });
  const faces = useInfiniteQuery({
    queryKey: ["personFaces", id],
    queryFn: ({ pageParam }) => api.personFaces(id, pageParam),
    initialPageParam: 0,
    getNextPageParam: (last, pages) => (last.has_more ? pages.length * PAGE : undefined),
    enabled: tab === "faces",
  });

  const rename = useMutation({
    mutationFn: (cover?: number) => api.renamePerson(id, editing ? name : person.data!.name, cover ?? person.data!.cover_face_id),
    onSuccess: () => { setEditing(false); refresh(); },
  });
  const notThem = useMutation({ mutationFn: (faceId: number) => api.updateFace(faceId, { clear: true }), onSuccess: refresh });
  const merge = useMutation({
    mutationFn: () => api.mergePerson(id, Number(mergeInto)),
    onSuccess: (p) => { refresh(); navigate(`/people/${p.id}`, { replace: true }); },
  });
  const del = useMutation({ mutationFn: () => api.deletePerson(id), onSuccess: () => { refresh(); navigate("/people"); } });

  if (person.isLoading) return <p className="muted">Loading…</p>;
  if (person.error || !person.data) return <p className="error">{String(person.error ?? "Not found")}</p>;
  const p = person.data;
  const list = photos.data?.pages.flatMap((pg) => pg.photos) ?? [];
  const years = photos.data?.pages[0]?.facets?.year ?? [];
  const faceList = faces.data?.pages.flatMap((pg) => pg.faces) ?? [];

  return (
    <>
      <div className="crumbs"><Link to="/people">People</Link></div>
      <div className="folder-header">
        <div className="person-header">
          {p.cover_url && <img className="person-cover" src={p.cover_url} alt="" />}
          <div>
            {editing ? (
              <form className="row" onSubmit={(e) => { e.preventDefault(); if (name.trim()) rename.mutate(undefined); }}>
                <input autoFocus value={name} onChange={(e) => setName(e.target.value)} />
                <button type="submit" className="primary" disabled={!name.trim()}>Save</button>
                <button type="button" className="link" onClick={() => setEditing(false)}>Cancel</button>
              </form>
            ) : (
              <h1>{p.name} <button className="link small" onClick={() => { setName(p.name); setEditing(true); }}>Rename</button></h1>
            )}
            <p className="muted">{p.photos.toLocaleString()} photos · {p.faces.toLocaleString()} faces</p>
            {rename.error && <p className="error small">{String(rename.error)}</p>}
          </div>
        </div>
        <div className="actions">
          <Link className="button primary" to={`/play?${queryParams(query, "date")}`}>▶ Through the years</Link>
          <Link className="button" to={`/search?${queryParams(query, "date")}`}>Search with {p.name}</Link>
        </div>
      </div>

      {years.length > 0 && (
        <div className="chips year-chips">
          {years.map((y) => (
            <Link key={y.value} className="chip" to={`/search?${queryParams({ ...query, year_from: Number(y.value), year_to: Number(y.value) }, "date")}`}>
              {y.value} <span className="muted">{y.count}</span>
            </Link>
          ))}
        </div>
      )}

      <div className="tabs">
        <button className={tab === "photos" ? "on" : ""} onClick={() => setTab("photos")}>Photos</button>
        <button className={tab === "faces" ? "on" : ""} onClick={() => setTab("faces")}>Faces (fix mistakes)</button>
      </div>

      {tab === "photos" ? (
        <>
          <PhotoTiles photos={list} onOpen={setOpen} />
          {photos.hasNextPage && <button className="more" onClick={() => photos.fetchNextPage()}>Load more</button>}
          {open != null && <Lightbox photos={list} index={open} onClose={() => setOpen(null)} onMove={setOpen} />}
        </>
      ) : (
        <>
          <p className="muted small">
            ✕ marks a face as not {p.name} (it won't be matched to them again). ★ uses it as their picture.
            Faces marked “auto” were matched automatically.
          </p>
          <div className="face-grid">
            {faceList.map((f) => (
              <div key={f.id} className="face-tile">
                <FaceCrop face={f} size={112} badge={f.assigned_by === "auto" ? "auto" : undefined} />
                <div className="face-tools">
                  <button title={`Not ${p.name}`} onClick={() => notThem.mutate(f.id)}>✕</button>
                  <button title="Use as their picture" className={p.cover_face_id === f.id ? "on" : ""}
                    onClick={() => rename.mutate(f.id)}>★</button>
                </div>
              </div>
            ))}
          </div>
          {faces.hasNextPage && <button className="more" onClick={() => faces.fetchNextPage()}>Load more</button>}
        </>
      )}

      <details className="danger-zone">
        <summary>Merge or delete</summary>
        <div className="row">
          <span>Same person as</span>
          <select value={mergeInto} onChange={(e) => setMergeInto(e.target.value)}>
            <option value="">choose…</option>
            {people.data?.filter((o) => o.id !== id).map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
          </select>
          <button disabled={!mergeInto || merge.isPending} onClick={() => merge.mutate()}>Merge into them</button>
        </div>
        <div className="row">
          {confirmDelete ? (
            <>
              <span>Forget {p.name}? Their faces become unnamed again.</span>
              <button className="danger" onClick={() => del.mutate()}>Forget</button>
              <button className="link" onClick={() => setConfirmDelete(false)}>Keep</button>
            </>
          ) : (
            <button className="link" onClick={() => setConfirmDelete(true)}>Forget this person…</button>
          )}
        </div>
      </details>
    </>
  );
}
