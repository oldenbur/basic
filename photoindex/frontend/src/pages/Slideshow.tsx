import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, eventTitle, Photo, Sort, ThemeQuery } from "../api";

const PAGE = 200;
const PREFETCH = 5;
const SPEEDS = [3, 5, 8, 12, 20];

function caption(p: Photo): string {
  const when = p.taken_at ?? p.event_date;
  const date = when ? new Date(when).toLocaleDateString(undefined, { month: "long", year: "numeric" }) : null;
  const where = p.abroad ? null : p.state;
  return [p.event_name && eventTitle(p.event_name), date, where].filter(Boolean).join(" · ");
}

/** Keep the screen on while playing (where the browser supports it). */
function useWakeLock(active: boolean) {
  useEffect(() => {
    if (!active || !("wakeLock" in navigator)) return;
    let lock: WakeLockSentinel | null = null;
    let cancelled = false;
    const acquire = () => navigator.wakeLock.request("screen").then((l) => {
      if (cancelled) l.release(); else lock = l;
    }, () => {});
    acquire();
    const onVisible = () => document.visibilityState === "visible" && acquire();
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      cancelled = true;
      document.removeEventListener("visibilitychange", onVisible);
      lock?.release();
    };
  }, [active]);
}

export function Slideshow() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const themeId = params.get("theme") ? Number(params.get("theme")) : null;
  const theme = useQuery({ queryKey: ["theme", themeId], queryFn: () => api.theme(themeId!), enabled: themeId != null });

  const query: ThemeQuery | undefined = themeId != null ? theme.data?.query : JSON.parse(params.get("q") ?? "{}");
  const sort: Sort = (params.get("sort") as Sort) ?? theme.data?.sort ?? "event_shuffle";
  const [seed] = useState(() => Math.floor(Math.random() * 2 ** 30)); // a new order every play

  const pages = useInfiniteQuery({
    queryKey: ["play", query, sort, seed],
    queryFn: ({ pageParam }) => api.search(query!, { sort, seed, offset: pageParam, limit: PAGE }),
    initialPageParam: 0,
    getNextPageParam: (last, all) => (last.has_more ? all.length * PAGE : undefined),
    enabled: query != null,
    staleTime: Infinity,
  });
  const photos = pages.data?.pages.flatMap((p) => p.photos) ?? [];
  const total = pages.data?.pages[0]?.total ?? photos.length;

  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState(5);
  const [captions, setCaptions] = useState(true);
  const [controls, setControls] = useState(true);
  const [loaded, setLoaded] = useState<string | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const hideTimer = useRef<number>();

  const current = photos[index];
  const go = useCallback((delta: number) => {
    setIndex((i) => {
      if (photos.length === 0) return 0;
      const n = i + delta;
      if (n >= photos.length) return pages.hasNextPage ? i : 0; // wrap to the start at the end
      return n < 0 ? photos.length - 1 : n;
    });
  }, [photos.length, pages.hasNextPage]);

  // Fetch the next page before we get to the end of this one.
  useEffect(() => {
    if (index > photos.length - 20 && pages.hasNextPage && !pages.isFetchingNextPage) pages.fetchNextPage();
  }, [index, photos.length, pages]);

  // Preload the next few large images so slides change instantly.
  useEffect(() => {
    for (let i = 1; i <= PREFETCH; i++) {
      const p = photos[(index + i) % Math.max(photos.length, 1)];
      if (p) new Image().src = p.display_url;
    }
  }, [index, photos]);

  // Advance once the current image has been on screen for `speed` seconds.
  const broken = current != null && failed === current.display_url;
  const ready = current != null && (loaded === current.display_url || broken);
  useEffect(() => {
    if (!playing || !ready) return;
    const t = window.setTimeout(() => go(1), speed * 1000);
    return () => clearTimeout(t);
  }, [playing, ready, speed, go, index]);

  useWakeLock(playing);

  const exit = useCallback(() => {
    if (document.fullscreenElement) document.exitFullscreen();
    if (window.history.length > 1) navigate(-1); else navigate("/themes");
  }, [navigate]);

  const toggleFullscreen = () =>
    document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen().catch(() => {});

  const poke = useCallback(() => {
    setControls(true);
    clearTimeout(hideTimer.current);
    hideTimer.current = window.setTimeout(() => setControls(false), 2500);
  }, []);
  useEffect(() => { poke(); return () => clearTimeout(hideTimer.current); }, [poke]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLSelectElement) return;
      poke();
      if (e.key === " ") { e.preventDefault(); setPlaying((p) => !p); }
      else if (e.key === "ArrowRight") go(1);
      else if (e.key === "ArrowLeft") go(-1);
      else if (e.key === "Escape" && !document.fullscreenElement) exit();
      else if (e.key === "f") toggleFullscreen();
      else if (e.key === "c") setCaptions((c) => !c);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go, exit, poke]);

  // Swipe left/right on touch screens; a tap shows the controls.
  const touchX = useRef<number | null>(null);
  const onTouchStart = (e: React.TouchEvent) => { touchX.current = e.touches[0].clientX; };
  const onTouchEnd = (e: React.TouchEvent) => {
    if (touchX.current == null) return;
    const dx = e.changedTouches[0].clientX - touchX.current;
    touchX.current = null;
    if (Math.abs(dx) > 50) go(dx < 0 ? 1 : -1); else poke();
  };

  const loading = (themeId != null && theme.isLoading) || pages.isLoading;
  const error = theme.error ?? pages.error;

  return (
    <div className={`slideshow ${controls ? "" : "hide-cursor"}`} onMouseMove={poke}
      onTouchStart={onTouchStart} onTouchEnd={onTouchEnd}>
      {error ? <p className="slide-message error">{String(error)}</p>
        : loading ? <p className="slide-message">Loading…</p>
        : !current ? <p className="slide-message">No photos match this theme.</p>
        : (
          <div className="slide" key={current.id}>
            {broken ? (
              // The large copy couldn't be made; the grid thumbnail is better than nothing.
              current.thumb_url && <img className="slide-img shown fallback" src={current.thumb_url} alt={current.name} />
            ) : (
              <>
                {current.thumb_url && !ready && <img className="slide-img placeholder" src={current.thumb_url} alt="" />}
                <img className={`slide-img ${ready ? "shown" : ""}`} src={current.display_url} alt={current.name}
                  onLoad={() => setLoaded(current.display_url)} onError={() => setFailed(current.display_url)} />
              </>
            )}
          </div>
        )}

      {captions && current && <div className="slide-caption">{caption(current)}</div>}

      <div className={`slide-controls ${controls ? "visible" : ""}`}>
        <button onClick={exit} title="Exit (Esc)">✕</button>
        <span className="slide-title">{theme.data?.name ?? "Slideshow"}</span>
        <span className="muted">{photos.length ? `${index + 1} / ${total.toLocaleString()}` : ""}</span>
        <span className="spacer" />
        <button onClick={() => go(-1)} title="Previous (←)">‹</button>
        <button onClick={() => setPlaying((p) => !p)} title="Play/pause (space)">{playing ? "❚❚" : "▶"}</button>
        <button onClick={() => go(1)} title="Next (→)">›</button>
        <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))} title="Seconds per photo">
          {SPEEDS.map((s) => <option key={s} value={s}>{s}s</option>)}
        </select>
        <button onClick={() => setCaptions((c) => !c)} title="Captions (c)" className={captions ? "on" : ""}>Aa</button>
        <button onClick={toggleFullscreen} title="Full screen (f)">⛶</button>
      </div>
    </div>
  );
}
