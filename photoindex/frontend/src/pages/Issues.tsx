import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

export function Issues() {
  const [severity, setSeverity] = useState<"all" | "error" | "warning">("all");
  const q = useQuery({ queryKey: ["issues"], queryFn: api.issues });
  if (q.isLoading) return <p className="muted">Loading…</p>;
  if (q.error) return <p className="error">{String(q.error)}</p>;
  const rows = (q.data ?? []).filter((f) => severity === "all" || f.issues.some((i) => i.severity === severity));
  return (
    <>
      <div className="folder-header">
        <h1>Naming issues</h1>
        <select value={severity} onChange={(e) => setSeverity(e.target.value as typeof severity)}>
          <option value="all">All</option>
          <option value="error">Errors</option>
          <option value="warning">Warnings</option>
        </select>
      </div>
      <p className="muted">
        {rows.length} folder{rows.length === 1 ? "" : "s"}. Renames are suggestions only; nothing in Dropbox is changed.
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>Folder</th><th>Issues</th><th>Suggested name</th><th>Photos</th></tr>
          </thead>
          <tbody>
            {rows.map((f) => (
              <tr key={f.id}>
                <td><Link to={`/folders/${f.id}`}>{f.path}</Link></td>
                <td>
                  {f.issues.map((i) => (
                    <div key={i.code} className={i.severity === "error" ? "error" : "warn"}>{i.message}</div>
                  ))}
                </td>
                <td>{f.suggested_name ? <code>{f.suggested_name}</code> : <span className="muted">—</span>}</td>
                <td className="num">{f.counts.photos.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
