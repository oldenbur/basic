import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { api, Face, Person } from "../api";

/** After a face edit the server re-matches in the background (~1s); refresh now and again once it's done. */
export function useFaceRefresh() {
  const qc = useQueryClient();
  return useCallback(() => {
    const keys = [["people"], ["person"], ["personFaces"], ["clusters"], ["review"], ["faceStats"], ["photoFaces"], ["search"]];
    const run = () => keys.forEach((queryKey) => qc.invalidateQueries({ queryKey }));
    run();
    setTimeout(run, 1500);
  }, [qc]);
}

export function usePeople() {
  return useQuery({ queryKey: ["people"], queryFn: api.people });
}

export function FaceCrop({ face, size = 96, onClick, selected, title, badge }: {
  face: Face; size?: number; onClick?: () => void; selected?: boolean; title?: string; badge?: string;
}) {
  const body = face.crop_url
    ? <img src={face.crop_url} alt="" loading="lazy" width={size} height={size} />
    : <span className="no-thumb" style={{ width: size, height: size }} />;
  const cls = `face-crop ${selected ? "excluded" : ""} ${onClick ? "clickable" : ""}`;
  return onClick ? (
    <button className={cls} onClick={onClick} title={title} style={{ width: size, height: size }}>
      {body}{badge && <span className="face-badge">{badge}</span>}
    </button>
  ) : (
    <span className={cls} title={title} style={{ width: size, height: size }}>
      {body}{badge && <span className="face-badge">{badge}</span>}
    </span>
  );
}

export type Who = { person_id?: number; name?: string };

/** Type a name: picks an existing person (case-insensitive) or creates a new one. */
export function PersonPicker({ people, onPick, placeholder = "Who is this?", busy, autoFocus, submitLabel = "Name" }: {
  people: Person[] | undefined; onPick: (who: Who) => void; placeholder?: string; busy?: boolean;
  autoFocus?: boolean; submitLabel?: string;
}) {
  const [text, setText] = useState("");
  const listId = "people-names";
  const submit = () => {
    const name = text.trim();
    if (!name) return;
    const existing = people?.find((p) => p.name.toLowerCase() === name.toLowerCase());
    onPick(existing ? { person_id: existing.id } : { name });
    setText("");
  };
  return (
    <form className="person-picker" onSubmit={(e) => { e.preventDefault(); submit(); }}>
      <input list={listId} placeholder={placeholder} value={text} autoFocus={autoFocus}
        onChange={(e) => setText(e.target.value)} />
      <datalist id={listId}>{people?.map((p) => <option key={p.id} value={p.name} />)}</datalist>
      <button type="submit" className="primary" disabled={!text.trim() || busy}>{submitLabel}</button>
    </form>
  );
}
