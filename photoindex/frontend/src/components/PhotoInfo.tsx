import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, CATEGORY_LABEL, queryParams, TAG_CATEGORIES, TagCategory } from "../api";

/** What the AI said about a photo, with your corrections: remove or add tags, turn it upright. */
export function PhotoInfo({ photoId }: { photoId: number }) {
  const qc = useQueryClient();
  const info = useQuery({ queryKey: ["photoAI", photoId], queryFn: () => api.photoAI(photoId) });
  const [cat, setCat] = useState<TagCategory>("activity");
  const [text, setText] = useState("");
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["photoAI", photoId] });
    qc.invalidateQueries({ queryKey: ["search"] });
    qc.invalidateQueries({ queryKey: ["tags"] });
  };
  const edit = useMutation({
    mutationFn: (body: { add?: string[]; remove?: number[] }) => api.editPhotoTags(photoId, body),
    onSuccess: (data) => { qc.setQueryData(["photoAI", photoId], data); setText(""); refresh(); },
  });
  const rotate = useMutation({
    mutationFn: (rotation: number) => api.rotate(photoId, rotation),
    onSuccess: () => { refresh(); qc.invalidateQueries({ queryKey: ["photoFaces"] }); },
  });
  const d = info.data;
  if (!d) return <div className="photo-info">{info.error ? <span className="error">{String(info.error)}</span> : "…"}</div>;
  const place = [d.place_name, d.place.city, d.place.region, d.place.country].filter(Boolean).join(", ");
  const turn = (by: number) => rotate.mutate((((d.rotation + by) % 360) + 360) % 360);
  return (
    <div className="photo-info" onClick={(e) => e.stopPropagation()}>
      {d.caption ? <p className="caption">{d.caption}</p> : (
        <p className="muted">{d.tag_status === "queued" ? "Being tagged…" : "Not tagged by the AI yet."}</p>
      )}
      <div className="row small">
        {d.aesthetic != null && <span title="The AI's 1-10 rating as a slideshow photo">Score {d.aesthetic}/10</span>}
        {place && <span title={`From ${d.place.source === "ai" ? "the AI's guess" : d.place.source}`}>{place}</span>}
        {d.model && <span className="muted">by {d.model}</span>}
        <span className="spacer" />
        <button onClick={() => turn(-90)} disabled={rotate.isPending} title="Turn left (only in this app)">↺</button>
        <button onClick={() => turn(90)} disabled={rotate.isPending} title="Turn right (only in this app)">↻</button>
      </div>
      {TAG_CATEGORIES.map((c) => {
        const tags = d.tags.filter((t) => t.category === c);
        return tags.length ? (
          <div key={c} className="info-tags">
            <span className="muted small">{CATEGORY_LABEL[c]}</span>
            {tags.map((t) => (
              <span key={t.id} className="chip tag-chip">
                <Link to={`/search?${queryParams({ tags: [t.key] }, "best")}`}>{t.value}</Link>
                <button className="link" title="Not in this photo" onClick={() => edit.mutate({ remove: [t.id] })}>×</button>
              </span>
            ))}
          </div>
        ) : null;
      })}
      <form className="row small" onSubmit={(e) => { e.preventDefault(); if (text.trim()) edit.mutate({ add: [`${cat}:${text.trim()}`] }); }}>
        <select value={cat} onChange={(e) => setCat(e.target.value as TagCategory)}>
          {TAG_CATEGORIES.map((c) => <option key={c} value={c}>{CATEGORY_LABEL[c]}</option>)}
        </select>
        <input placeholder="Add a tag" value={text} onChange={(e) => setText(e.target.value)} />
        <button type="submit" disabled={!text.trim() || edit.isPending}>Add</button>
        {(edit.error || rotate.error) && <span className="error">{(edit.error ?? rotate.error)?.message}</span>}
      </form>
    </div>
  );
}
