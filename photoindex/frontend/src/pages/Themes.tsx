import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, SORT_LABEL, Theme } from "../api";

function ThemeCard({ t }: { t: Theme }) {
  const qc = useQueryClient();
  const [confirm, setConfirm] = useState(false);
  const refresh = () => qc.invalidateQueries({ queryKey: ["themes"] });
  const prepare = useMutation({ mutationFn: () => api.prepareTheme(t.id), onSuccess: refresh });
  const del = useMutation({ mutationFn: () => api.deleteTheme(t.id), onSuccess: refresh });
  const prepared = t.prepared ?? 0;
  const allPrepared = t.count > 0 && prepared >= t.count;
  return (
    <div className="theme-card">
      <Link to={`/play?theme=${t.id}`} className="cover" title="Play">
        {t.cover_url ? <img src={t.cover_url} alt="" loading="lazy" /> : <div className="no-thumb">No photos</div>}
        <span className="play-overlay">▶</span>
      </Link>
      <div className="theme-body">
        <div className="folder-name">{t.name}</div>
        <div className="folder-counts">
          {t.count.toLocaleString()} photos · {SORT_LABEL[t.sort] ?? t.sort}
        </div>
        <div className="folder-counts" title="Large slideshow images already made. The rest are made as they're first shown.">
          {t.preparing ? `Preparing… ${prepared.toLocaleString()} / ${t.count.toLocaleString()}`
            : allPrepared ? "Ready for smooth playback" : `${prepared.toLocaleString()} / ${t.count.toLocaleString()} prepared`}
        </div>
        <div className="theme-actions">
          <Link className="button primary" to={`/play?theme=${t.id}`}>▶ Play</Link>
          <Link className="button" to={`/search?theme=${t.id}`}>Edit</Link>
          {!allPrepared && (
            <button onClick={() => prepare.mutate()} disabled={t.preparing || prepare.isPending}
              title="Make every large image now, so the first showing is as smooth as later ones">
              Prepare
            </button>
          )}
          {confirm ? (
            <>
              <button className="danger" onClick={() => del.mutate()} disabled={del.isPending}>Delete</button>
              <button className="link" onClick={() => setConfirm(false)}>Keep</button>
            </>
          ) : (
            <button className="link" onClick={() => setConfirm(true)}>Delete…</button>
          )}
        </div>
      </div>
    </div>
  );
}

export function Themes() {
  const q = useQuery({
    queryKey: ["themes"],
    queryFn: api.themes,
    // Poll while any theme is preparing so its progress moves.
    refetchInterval: (query) => (query.state.data?.some((t) => t.preparing) ? 3000 : false),
  });
  if (q.isLoading) return <p className="muted">Loading…</p>;
  if (q.error) return <p className="error">{String(q.error)}</p>;
  const themes = q.data ?? [];
  return (
    <>
      <div className="folder-header">
        <div>
          <h1>Themes</h1>
          <p className="muted">Saved searches you can play as slideshows.</p>
        </div>
        <Link className="button primary" to="/search">New theme</Link>
      </div>
      {themes.length === 0 ? (
        <p className="muted">
          No themes yet. Build a search and choose “Save as theme”, or run <code>photoindex seed-themes</code> for a
          starter set drafted from your event names.
        </p>
      ) : (
        <div className="themes">{themes.map((t) => <ThemeCard key={t.id} t={t} />)}</div>
      )}
    </>
  );
}
