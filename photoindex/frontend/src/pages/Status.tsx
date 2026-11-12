import { useQuery } from "@tanstack/react-query";
import { api } from "../api";

const ROWS: [string, string][] = [
  ["folders", "Folders"],
  ["folders_with_issues", "Folders with naming issues"],
  ["photos", "Photos indexed"],
  ["highlight_copies", "Highlight copies"],
  ["highlights_linked", "…linked to their original"],
  ["highlights_unmatched", "…with no original (processed on their own)"],
  ["highlights_ambiguous", "…waiting on EXIF to resolve"],
  ["processing_set", "Processing set"],
  ["meta_done", "EXIF read"],
  ["thumbs_done", "Thumbnails stored"],
  ["burst_groups", "Burst groups"],
  ["date_mismatches", "Photos >1 day from their event date"],
  ["meta_errors", "EXIF errors"],
  ["thumb_errors", "Thumbnail errors"],
];

export function Status() {
  const q = useQuery({ queryKey: ["stats"], queryFn: api.stats, refetchInterval: 10_000 });
  if (q.isLoading) return <p className="muted">Loading…</p>;
  if (q.error || !q.data) return <p className="error">{String(q.error)}</p>;
  const s = q.data;
  const pct = (n: number) => (s.processing_set ? Math.round((100 * n) / s.processing_set) : 0);
  return (
    <>
      <h1>Pipeline</h1>
      <div className="progress-row">
        <div>EXIF <progress max={100} value={pct(s.meta_done)} /> {pct(s.meta_done)}%</div>
        <div>Thumbnails <progress max={100} value={pct(s.thumbs_done)} /> {pct(s.thumbs_done)}%</div>
      </div>
      <div className="table-wrap">
        <table className="stats">
          <tbody>
            {ROWS.map(([k, label]) => (
              <tr key={k}><td>{label}</td><td className="num">{(s[k] ?? 0).toLocaleString()}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
