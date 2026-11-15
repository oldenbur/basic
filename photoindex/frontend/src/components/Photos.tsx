import { useMutation, useQuery } from "@tanstack/react-query";
import { ReactNode, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, eventTitle, Face, Photo } from "../api";
import { PersonPicker, useFaceRefresh, usePeople, Who } from "./People";
import { PhotoInfo } from "./PhotoInfo";

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
export function LargeImage({ photo, className, overlay }: { photo: Photo; className?: string; overlay?: ReactNode }) {
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
      <div className="full-wrap">
        <img key={photo.display_url} className={ready ? "full shown" : "full"} src={photo.display_url} alt={photo.name}
          onLoad={() => setLoaded(photo.display_url)} onError={() => setFailed(photo.display_url)} />
        {ready && overlay}
      </div>
    </div>
  );
}

/** Boxes over each detected face; click one to say who it is. Boxes are fractions of the display image. */
function FaceBoxes({ photoId }: { photoId: number }) {
  const faces = useQuery({ queryKey: ["photoFaces", photoId], queryFn: () => api.photoFaces(photoId) });
  const people = usePeople();
  const refresh = useFaceRefresh();
  const [editing, setEditing] = useState<number | null>(null);
  const update = useMutation({
    mutationFn: ({ face, body }: { face: Face; body: Who | { clear: true } | { ignored: true } }) => api.updateFace(face.id, body),
    onSuccess: () => { setEditing(null); refresh(); },
  });
  return (
    <>
      {faces.data?.filter((f) => !f.ignored).map((f) => {
        const [x, y, w, h] = f.box;
        const label = f.person_name ?? (f.suggested_name ? `${f.suggested_name}?` : null);
        return (
          <div key={f.id} className={`face-box ${f.person_name ? "named" : ""}`}
            style={{ left: `${x * 100}%`, top: `${y * 100}%`, width: `${w * 100}%`, height: `${h * 100}%` }}
            onClick={(e) => { e.stopPropagation(); setEditing(editing === f.id ? null : f.id); }}>
            {label && <span className="face-label">{label}{f.assigned_by === "auto" ? " ·auto" : ""}</span>}
            {editing === f.id && (
              <div className="face-pop" onClick={(e) => e.stopPropagation()}>
                <PersonPicker people={people.data} autoFocus busy={update.isPending}
                  placeholder={f.person_name ? `Not ${f.person_name}? Who…` : "Who is this?"}
                  onPick={(who) => update.mutate({ face: f, body: who })} />
                <div className="row">
                  {f.person_name && <button className="link" onClick={() => update.mutate({ face: f, body: { clear: true } })}>Not {f.person_name}</button>}
                  <button className="link" onClick={() => update.mutate({ face: f, body: { ignored: true } })}>Not someone I need</button>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </>
  );
}

export function Lightbox({ photos, index, onClose, onMove }: {
  photos: Photo[]; index: number; onClose: () => void; onMove: (i: number) => void;
}) {
  const p = photos[index];
  const [showFaces, setShowFaces] = useState(false);
  const [showInfo, setShowInfo] = useState(false);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) return; // typing a name/tag
      if (e.key === "f") setShowFaces((s) => !s);
      if (e.key === "i") setShowInfo((s) => !s);
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
      <figure className={showInfo ? "with-info" : ""} onClick={(e) => e.stopPropagation()}>
        <LargeImage photo={p} overlay={showFaces && p.face_count ? <FaceBoxes photoId={p.id} /> : null} />
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
          {p.face_count != null && p.face_count > 0 && (
            <button className={`link ${showFaces ? "on" : ""}`} onClick={() => setShowFaces((s) => !s)} title="Show faces (F)">
              {showFaces ? "Hide faces" : `${p.face_count} face${p.face_count > 1 ? "s" : ""}`}
            </button>
          )}
          <button className={`link ${showInfo ? "on" : ""}`} onClick={() => setShowInfo((s) => !s)} title="Caption, tags, place (I)">
            {showInfo ? "Hide details" : "Details"}
          </button>
          <a href={api.originalUrl(p.id)} target="_blank" rel="noreferrer">Open original</a>
        </figcaption>
        {showInfo ? <PhotoInfo photoId={p.id} /> : p.caption && <p className="lightbox-caption">{p.caption}</p>}
      </figure>
    </div>
  );
}
