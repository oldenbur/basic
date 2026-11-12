import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, Folder, Photo } from "../api";

const KIND_LABEL: Record<string, string> = {
  year: "Year", event: "Event", highlights: "Highlights", event_sub: "Subfolder", highlights_sub: "Highlights", other: "Other",
};

function FolderCard({ f }: { f: Folder }) {
  const hasErrors = f.issues.some((i) => i.severity === "error");
  return (
    <Link to={`/folders/${f.id}`} className={`folder-card kind-${f.kind ?? "other"}`}>
      <div className="folder-name">{f.name}</div>
      <div className="folder-meta">
        <span className="pill">{KIND_LABEL[f.kind ?? "other"] ?? f.kind}</span>
        {f.state && <span className="pill">{f.state}</span>}
        {f.issues.length > 0 && (
          <span className={`pill ${hasErrors ? "pill-error" : "pill-warn"}`} title={f.issues.map((i) => i.message).join("\n")}>
            {f.issues.length} issue{f.issues.length > 1 ? "s" : ""}
          </span>
        )}
      </div>
      <div className="folder-counts">
        {f.counts.photos.toLocaleString()} photos
        {f.counts.processing > 0 && <> · {f.counts.processing.toLocaleString()} in set</>}
      </div>
    </Link>
  );
}

function Lightbox({ photos, index, onClose, onMove }: {
  photos: Photo[]; index: number; onClose: () => void; onMove: (i: number) => void;
}) {
  const p = photos[index];
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowRight" && index < photos.length - 1) onMove(index + 1);
      if (e.key === "ArrowLeft" && index > 0) onMove(index - 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [index, photos.length, onClose, onMove]);

  return (
    <div className="lightbox" onClick={onClose}>
      <figure onClick={(e) => e.stopPropagation()}>
        {p.thumb_url ? <img src={p.thumb_url} alt={p.name} /> : <div className="no-thumb large">No thumbnail yet</div>}
        <figcaption>
          <strong>{p.name}</strong>
          {p.taken_at && <span>{new Date(p.taken_at).toLocaleString()}</span>}
          {p.camera && <span>{p.camera}</span>}
          {p.lat != null && <span>{p.lat.toFixed(3)}, {p.lon?.toFixed(3)}</span>}
          {p.date_mismatch_days != null && p.date_mismatch_days > 1 && (
            <span className="pill pill-warn">{p.date_mismatch_days} days from event date</span>
          )}
          <a href={api.originalUrl(p.id)} target="_blank" rel="noreferrer">Open original</a>
        </figcaption>
      </figure>
    </div>
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
      <div className="grid">
        {photos.map((p, i) => (
          <button key={p.id} className="tile" onClick={() => setOpen(i)} title={p.name}>
            {p.thumb_url ? <img src={p.thumb_url} alt={p.name} loading="lazy" /> : <div className="no-thumb">{p.name}</div>}
            <span className="badges">
              {p.has_highlight && <span className="badge" title="Has a highlight copy">★</span>}
              {p.is_highlight_copy && p.link_method === "none" && <span className="badge" title="No original found">?</span>}
              {p.burst_group_id != null && <span className="badge" title="Part of a burst">⧉</span>}
            </span>
          </button>
        ))}
      </div>
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
            {folder.counts.photos.toLocaleString()} photos · {folder.counts.processing.toLocaleString()} in processing set
          </p>
          {folder.issues.map((i) => (
            <p key={i.code} className={i.severity === "error" ? "error" : "warn"}>
              {i.message}{folder.suggested_name && <> — suggested: <code>{folder.suggested_name}</code></>}
            </p>
          ))}
        </div>
        {folder.kind !== "highlights" && folder.kind !== "highlights_sub" && (
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

export function Browse() {
  const { id } = useParams();
  const tree = useQuery({ queryKey: ["tree"], queryFn: api.tree, enabled: !id });
  if (id) return <FolderView id={Number(id)} key={id} />;
  if (tree.isLoading) return <p className="muted">Loading…</p>;
  if (tree.error) return <p className="error">{String(tree.error)}</p>;
  if (!tree.data?.length) return <p className="muted">Library is empty. Run <code>photoindex run</code> to index it.</p>;
  return (
    <>
      <h1>Library</h1>
      <div className="folders">{tree.data.map((f) => <FolderCard key={f.id} f={f} />)}</div>
    </>
  );
}
