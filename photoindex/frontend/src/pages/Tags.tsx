import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, CATEGORY_LABEL, queryParams, TAG_CATEGORIES, TagCategory, TagItem } from "../api";

function TagRow({ tag, others }: { tag: TagItem; others: TagItem[] }) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(tag.value);
  const [mergeInto, setMergeInto] = useState("");
  const [merging, setMerging] = useState(false);
  const edit = useMutation({
    mutationFn: (body: { value?: string; hidden?: boolean; merge_into_id?: number }) => api.editTag(tag.id, body),
    onSuccess: () => { setEditing(false); qc.invalidateQueries({ queryKey: ["tags"] }); qc.invalidateQueries({ queryKey: ["search"] }); },
  });
  return (
    <tr className={tag.hidden ? "muted" : ""}>
      <td>
        {editing ? (
          <form className="row" onSubmit={(e) => { e.preventDefault(); if (value.trim()) edit.mutate({ value }); }}>
            <input autoFocus value={value} onChange={(e) => setValue(e.target.value)} />
            <button type="submit" disabled={!value.trim() || edit.isPending}>Rename</button>
            <button type="button" className="link" onClick={() => setEditing(false)}>Cancel</button>
          </form>
        ) : (
          <Link to={`/search?${queryParams({ tags: [tag.key] }, "best")}`}>{tag.value}</Link>
        )}
        {edit.error && <span className="error small"> {edit.error.message}</span>}
      </td>
      <td className="num">{tag.count.toLocaleString()}</td>
      <td>
        <div className="row">
          {!editing && <button className="link" onClick={() => setEditing(true)} title="Renaming onto an existing tag merges them">Rename</button>}
          {merging ? (
            <>
              <select autoFocus value={mergeInto} onChange={(e) => setMergeInto(e.target.value)}>
                <option value="">same as…</option>
                {others.map((o) => <option key={o.id} value={o.id}>{o.value} ({o.count})</option>)}
              </select>
              <button onClick={() => edit.mutate({ merge_into_id: Number(mergeInto) })} disabled={!mergeInto || edit.isPending}>Merge</button>
              <button className="link" onClick={() => setMerging(false)}>Cancel</button>
            </>
          ) : (
            <button className="link" onClick={() => setMerging(true)} title="Same thing as another tag">Merge…</button>
          )}
          <button className="link" onClick={() => edit.mutate({ hidden: !tag.hidden })}>{tag.hidden ? "Show" : "Hide"}</button>
        </div>
      </td>
    </tr>
  );
}

export function Tags() {
  const tags = useQuery({ queryKey: ["tags"], queryFn: api.tags });
  const [cat, setCat] = useState<TagCategory>("activity");
  const [filter, setFilter] = useState("");
  const all = tags.data ?? [];
  const inCat = all.filter((t) => t.category === cat);
  const shown = inCat.filter((t) => t.value.toLowerCase().includes(filter.toLowerCase()));
  return (
    <>
      <div className="crumbs"><Link to="/tagging">AI tags</Link></div>
      <h1>Tags</h1>
      <p className="muted">
        What the AI tagged, most common first. Merge tags that mean the same thing (future answers follow the merge),
        rename awkward ones, and hide ones that aren't useful for searching.
      </p>
      <div className="tabs">
        {TAG_CATEGORIES.map((c) => (
          <button key={c} className={cat === c ? "on" : ""} onClick={() => { setCat(c); setFilter(""); }}>
            {CATEGORY_LABEL[c]} <span className="muted">{all.filter((t) => t.category === c).length}</span>
          </button>
        ))}
      </div>
      <input type="search" placeholder="Filter" value={filter} onChange={(e) => setFilter(e.target.value)} />
      {tags.isLoading ? <p className="muted">Loading…</p> : shown.length === 0 ? <p className="muted">No tags yet.</p> : (
        <div className="table-wrap">
          <table className="tag-table">
            <thead><tr><th>Tag</th><th className="num">Photos</th><th /></tr></thead>
            <tbody>
              {shown.map((t) => <TagRow key={t.id} tag={t} others={inCat.filter((o) => o.id !== t.id)} />)}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
