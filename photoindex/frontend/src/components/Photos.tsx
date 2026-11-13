import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, eventTitle, Photo } from "../api";

export function PhotoTiles({ photos, onOpen }: { photos: Photo[]; onOpen: (i: number) => void }) {
  return (
    <div className="grid">
      {photos.map((p, i) => (
        <button key={p.id} className="tile" onClick={() => onOpen(i)} title={p.event_name ? `${p.event_name} · ${p.name}` : p.name}>
          {p.thumb_url ? <img src={p.thumb_url} alt={p.name} loading="lazy" /> : <div className="no-thumb">{p.name}</div>}
          <span className="badges">
            {p.has_highlight && <span className="badge" title="Has a highlight copy">★</span>}
            {p.is_highlight_copy && p.link_method === "none" && <span className="badge" title="No original found">?</span>}
            {p.burst_group_id != null && <span className="badge" title="Part of a burst">⧉</span>}
          </span>
        </button>
      ))}
    </div>
  );
}

/** Thumbnail first (already cached by the grid), then the 2048px copy fades in over it once loaded. */
export function LargeImage({ photo, className }: { photo: Photo; className?: string }) {
  const [loaded, setLoaded] = useState<string | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const ready = loaded === photo.display_url;
  if (failed === photo.display_url) {
    return <div className={`large-image ${className ?? ""}`}>
      {photo.thumb_url ? <img src={photo.thumb_url} alt={photo.name} /> : <div className="no-thumb large">No image</div>}
    </div>;
  }
  return (
    <div className={`large-image ${className ?? ""}`}>
      {photo.thumb_url && !ready && <img className="placeholder" src={photo.thumb_url} alt="" />}
      <img key={photo.display_url} className={ready ? "full shown" : "full"} src={photo.display_url} alt={photo.name}
        onLoad={() => setLoaded(photo.display_url)} onError={() => setFailed(photo.display_url)} />
    </div>
  );
}

export function Lightbox({ photos, index, onClose, onMove }: {
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
  // Warm the neighbours so arrowing through is instant.
  useEffect(() => {
    for (const n of [photos[index + 1], photos[index - 1]]) if (n) new Image().src = n.display_url;
  }, [index, photos]);

  return (
    <div className="lightbox" onClick={onClose}>
      <figure onClick={(e) => e.stopPropagation()}>
        <LargeImage photo={p} />
        <figcaption>
          {p.event_name && p.event_folder_id != null && <Link to={`/folders/${p.event_folder_id}`}>{eventTitle(p.event_name)}</Link>}
          <strong>{p.name}</strong>
          {p.taken_at && <span>{new Date(p.taken_at).toLocaleString()}</span>}
          {p.camera && <span>{p.camera}</span>}
          {p.lat != null && <span>{p.lat.toFixed(3)}, {p.lon?.toFixed(3)}</span>}
          {p.date_mismatch_days != null && Math.abs(p.date_mismatch_days) > 30 && (
            <span className="pill pill-warn">
              {Math.abs(p.date_mismatch_days)} days {p.date_mismatch_days < 0 ? "before" : "after"} event date
            </span>
          )}
          <a href={api.originalUrl(p.id)} target="_blank" rel="noreferrer">Open original</a>
        </figcaption>
      </figure>
    </div>
  );
}
