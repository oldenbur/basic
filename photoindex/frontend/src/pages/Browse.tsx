import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, Folder } from "../api";
import { Lightbox, PhotoTiles } from "../components/Photos";

const KIND_LABEL: Record<string, string> = {
  year: "Year", event: "Event", highlights: "Highlights", event_sub: "Subfolder", highlights_sub: "Highlights",
};

const isHighlights = (f: Folder) => f.kind === "highlights" || f.kind === "highlights_sub";

function CountsLine({ f, long }: { f: Folder; long?: boolean }) {
  const c = f.counts;
  if (isHighlights(f)) {
    // A copy isn't processed itself (its original is), so "in set" means nothing here.
    const unmatched = c.highlights - c.linked;
    return <>{c.highlights.toLocaleString()} copies · {c.linked.toLocaleString()} linked to originals
      {unmatched > 0 && <> · {unmatched.toLocaleString()} without one</>}</>;
  }
  return <>{c.photos.toLocaleString()} photos
    {(long || c.processing > 0) && <> · {c.processing.toLocaleString()} in {long ? "processing " : ""}set</>}</>;
}

function FolderCard({ f }: { f: Folder }) {
  return (
    <Link to={`/folders/${f.id}`} className={`folder-card kind-${f.kind ?? "other"}`}>
      <div className="folder-name">{f.name}</div>
      <div className="folder-meta">
        <span className="pill">{KIND_LABEL[f.kind ?? "other"] ?? f.kind}</span>
        {f.state && <span className="pill">{f.state}</span>}
        {f.abroad && <span className="pill">abroad</span>}
        {f.issues.length > 0 && (
          <span className="pill pill-warn" title={f.issues.map((i) => i.message).join("\n")}>
            {f.issues.length} issue{f.issues.length > 1 ? "s" : ""}
          </span>
        )}
      </div>
      <div className="folder-counts">
        <CountsLine f={f} />
      </div>
    </Link>
  );
}

function PhotoGrid({ folderId }: { folderId: number }) {
  const [open, setOpen] = useState<number | null>(null);
  const q = useInfiniteQuery({
    queryKey: ["photos", folderId],
    queryFn: ({ pageParam }) => api.photos(folderId, pageParam),
    initialPageParam: 0,
    getNextPageParam: (last, pages) => (last.has_more ? pages.length * 200 : undefined),
  });
  const photos = q.data?.pages.flatMap((p) => p.photos) ?? [];
  if (q.isLoading) return <p className="muted">Loading photos…</p>;
  if (photos.length === 0) return null;
  return (
    <>
      <PhotoTiles photos={photos} onOpen={setOpen} />
      {q.hasNextPage && (
        <button className="more" onClick={() => q.fetchNextPage()} disabled={q.isFetchingNextPage}>
          {q.isFetchingNextPage ? "Loading…" : "Load more"}
        </button>
      )}
      {open != null && <Lightbox photos={photos} index={open} onClose={() => setOpen(null)} onMove={setOpen} />}
    </>
  );
}

function FolderView({ id }: { id: number }) {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["folder", id], queryFn: () => api.folder(id) });
  const scope = useMutation({
    mutationFn: (inScope: boolean) => api.setScope(id, inScope),
    onSuccess: () => qc.invalidateQueries(),
  });
  if (q.isLoading) return <p className="muted">Loading…</p>;
  if (q.error || !q.data) return <p className="error">{String(q.error)}</p>;
  const { folder, children, breadcrumbs } = q.data;
  return (
    <>
      <div className="crumbs">
        <Link to="/">Library</Link>
        {breadcrumbs.map((b) => (
          <span key={b.id}> / <Link to={`/folders/${b.id}`}>{b.name}</Link></span>
        ))}
      </div>
      <div className="folder-header">
        <div>
          <h1>{folder.event_name ?? folder.name}</h1>
          <p className="muted">
            {folder.event_date && <>{new Date(folder.event_date + "T00:00").toLocaleDateString()} · </>}
            {folder.state && <>{folder.state} · </>}
            {folder.abroad && <>outside the US · </>}
            <CountsLine f={folder} long />
          </p>
          {folder.issues.map((i) => (
            <p key={i.code} className="warn">
              {i.message}{folder.suggested_name && <> — suggested: <code>{folder.suggested_name}</code></>}
            </p>
          ))}
        </div>
        {!isHighlights(folder) && (
          <label className="scope-toggle" title="Process every photo in this folder (thumbnails, faces, AI tags), not just highlights">
            <input type="checkbox" checked={folder.in_scope} disabled={scope.isPending}
              onChange={(e) => scope.mutate(e.target.checked)} />
            Process all photos here
          </label>
        )}
      </div>
      {children.length > 0 && <div className="folders">{children.map((c) => <FolderCard key={c.id} f={c} />)}</div>}
      <PhotoGrid folderId={id} />
    </>
  );
}

function OnThisDay() {
  const today = new Date();
  const q = useQuery({ queryKey: ["onthisday", today.toDateString()], queryFn: () => api.onThisDay(today) });
  const [open, setOpen] = useState<number | null>(null);
  const photos = q.data ?? [];
  if (photos.length === 0) return null;
  const years = new Set(photos.map((p) => p.taken_at?.slice(0, 4)));
  return (
    <section className="onthisday">
      <h2>On this day <span className="muted">· {years.size} year{years.size > 1 ? "s" : ""}</span></h2>
      <div className="strip">
        {photos.map((p, i) => (
          <button key={p.id} className="tile" onClick={() => setOpen(i)} title={p.event_name}>
            {p.thumb_url && <img src={p.thumb_url} alt={p.name} loading="lazy" />}
            <span className="year-label">{p.taken_at?.slice(0, 4)}</span>
          </button>
        ))}
      </div>
      {open != null && <Lightbox photos={photos} index={open} onClose={() => setOpen(null)} onMove={setOpen} />}
    </section>
  );
}

export function Browse() {
  const { id } = useParams();
  const tree = useQuery({ queryKey: ["tree"], queryFn: api.tree, enabled: !id });
  if (id) return <FolderView id={Number(id)} key={id} />;
  if (tree.isLoading) return <p className="muted">Loading…</p>;
  if (tree.error) return <p className="error">{String(tree.error)}</p>;
  if (!tree.data?.length) return <p className="muted">Library is empty. Run <code>photoindex run</code> to index it.</p>;
  return (
    <>
      <OnThisDay />
      <h1>Library</h1>
      <div className="folders">{tree.data.map((f) => <FolderCard key={f.id} f={f} />)}</div>
    </>
  );
}
