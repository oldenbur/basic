import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, CATEGORY_LABEL, Facet, queryParams, Sort, SORT_LABEL, TAG_CATEGORIES, tagLabel, Theme, ThemeQuery } from "../api";
import { usePeople } from "../components/People";
import { Lightbox, PhotoTiles } from "../components/Photos";

const PAGE = 200;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const SEASONS: [string, number[]][] = [
  ["Winter", [12, 1, 2]], ["Spring", [3, 4, 5]], ["Summer", [6, 7, 8]], ["Fall", [9, 10, 11]],
];
const FIRST_YEAR = 1995;
const YEARS = Array.from({ length: new Date().getFullYear() - FIRST_YEAR + 1 }, (_, i) => FIRST_YEAR + i);

function parseQuery(raw: string | null): ThemeQuery {
  try {
    return raw ? (JSON.parse(raw) as ThemeQuery) : {};
  } catch {
    return {};
  }
}

/** Drop empty/default fields so URLs and saved themes stay small. */
function compact(q: ThemeQuery): ThemeQuery {
  const out: ThemeQuery = {};
  if (q.text?.trim()) out.text = q.text.trim();
  if (q.year_from != null) out.year_from = q.year_from;
  if (q.year_to != null) out.year_to = q.year_to;
  if (q.months?.length) out.months = q.months;
  if (q.states?.length) out.states = q.states;
  if (q.cameras?.length) out.cameras = q.cameras;
  if (q.folder_ids?.length) out.folder_ids = q.folder_ids;
  if (q.has_gps != null) out.has_gps = q.has_gps;
  if (q.highlights_only) out.highlights_only = true;
  if (q.collapse_bursts === false) out.collapse_bursts = false;
  if (q.people?.length) out.people = q.people;
  if (q.people_all && (q.people?.length ?? 0) > 1) out.people_all = true;
  if (q.group) out.group = q.group;
  if (q.tags?.length) out.tags = q.tags;
  if (q.countries?.length) out.countries = q.countries;
  if (q.regions?.length) out.regions = q.regions;
  if (q.min_score != null) out.min_score = q.min_score;
  return out;
}

const toggle = <T,>(list: T[] | undefined, v: T) =>
  list?.includes(v) ? list.filter((x) => x !== v) : [...(list ?? []), v];

function Chips({ facets, selected, label, numeric, onToggle }: {
  facets: Facet[] | undefined; selected: (string | number)[] | undefined; label?: (v: string | number) => string;
  numeric?: boolean; onToggle: (v: string | number) => void;
}) {
  const counts = new Map((facets ?? []).map((f) => [f.value, f.count]));
  // Facets arrive most-common first; selected values with no photos left still show (at the end) so they can be
  // turned off. Months stay in calendar order.
  const values = [...new Set([...counts.keys(), ...(selected ?? [])])];
  if (numeric) values.sort((a, b) => Number(a) - Number(b));
  if (values.length === 0) return <p className="muted small">None</p>;
  return (
    <div className="chips">
      {values.map((v) => (
        <button key={String(v)} className={`chip ${selected?.includes(v) ? "on" : ""}`} onClick={() => onToggle(v)}>
          {label ? label(v) : String(v)} <span className="muted">{(counts.get(v) ?? 0).toLocaleString()}</span>
        </button>
      ))}
    </div>
  );
}

/** Tag chips for one category: the most common few, the rest behind "more". */
function TagChips({ facets, selected, onToggle }: {
  facets: Facet[] | undefined; selected: string[] | undefined; onToggle: (v: string) => void;
}) {
  const [all, setAll] = useState(false);
  const list = facets ?? [];
  const shown = all ? list : list.filter((f, i) => i < 10 || selected?.includes(String(f.value)));
  const label = (v: string | number) => list.find((f) => f.value === v)?.label ?? tagLabel(String(v));
  return (
    <>
      <Chips facets={shown} selected={selected} label={label} onToggle={(v) => onToggle(String(v))} />
      {list.length > 10 && <button className="link small" onClick={() => setAll(!all)}>{all ? "fewer" : `${list.length - 10} more`}</button>}
    </>
  );
}

function SaveTheme({ query, sort, theme }: { query: ThemeQuery; sort: Sort; theme: Theme | undefined }) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [open, setOpen] = useState(false);
  const save = useMutation({
    mutationFn: (asNew: boolean) => {
      const body = { name: asNew ? name : theme!.name, query, sort, cover_photo_id: theme?.cover_photo_id };
      return asNew || !theme ? api.createTheme(body) : api.updateTheme(theme.id, body);
    },
    onSuccess: (t) => {
      qc.invalidateQueries({ queryKey: ["themes"] });
      qc.setQueryData(["theme", t.id], t);
      setOpen(false);
      navigate(`/search?theme=${t.id}`, { replace: true });
    },
  });
  return (
    <div className="save-theme">
      {theme && (
        <button onClick={() => save.mutate(false)} disabled={save.isPending}>Update “{theme.name}”</button>
      )}
      {open ? (
        <form onSubmit={(e) => { e.preventDefault(); if (name.trim()) save.mutate(true); }}>
          <input autoFocus placeholder="Theme name" value={name} onChange={(e) => setName(e.target.value)} />
          <button type="submit" disabled={!name.trim() || save.isPending}>Save</button>
          <button type="button" className="link" onClick={() => setOpen(false)}>Cancel</button>
        </form>
      ) : (
        <button onClick={() => setOpen(true)}>{theme ? "Save as new theme" : "Save as theme"}</button>
      )}
      {save.error && <span className="error small">{save.error.message}</span>}
    </div>
  );
}

export function Search() {
  const [params, setParams] = useSearchParams();
  const people = usePeople();
  const themeId = params.get("theme") ? Number(params.get("theme")) : null;
  const theme = useQuery({ queryKey: ["theme", themeId], queryFn: () => api.theme(themeId!), enabled: themeId != null });

  const [query, setQuery] = useState<ThemeQuery>(() => parseQuery(params.get("q")));
  const [sort, setSort] = useState<Sort>((params.get("sort") as Sort) ?? "date");
  const [text, setText] = useState(query.text ?? "");
  const [seed] = useState(() => Math.floor(Math.random() * 2 ** 30));
  const [open, setOpen] = useState<number | null>(null);
  const [wide] = useState(() => window.matchMedia("(min-width: 761px)").matches); // filters start collapsed on phones

  // Editing a theme: start from its saved query (once), unless the link carried its own query.
  const [linkHadQuery] = useState(() => params.has("q"));
  const [loadedTheme, setLoadedTheme] = useState<number | null>(null);
  useEffect(() => {
    if (theme.data && loadedTheme !== theme.data.id) {
      setLoadedTheme(theme.data.id);
      if (!linkHadQuery) {
        setQuery(theme.data.query);
        setText(theme.data.query.text ?? "");
        setSort(theme.data.sort);
      }
    }
  }, [theme.data, loadedTheme, linkHadQuery]);

  // Debounce typing into the query.
  useEffect(() => {
    const t = setTimeout(() => setQuery((q) => (q.text === text ? q : { ...q, text })), 300);
    return () => clearTimeout(t);
  }, [text]);

  const q = useMemo(() => compact(query), [query]);
  useEffect(() => {
    const next = new URLSearchParams(queryParams(q, sort));
    if (themeId != null) next.set("theme", String(themeId));
    setParams(next, { replace: true });
  }, [q, sort, themeId, setParams]);

  const results = useInfiniteQuery({
    queryKey: ["search", q, sort, seed],
    queryFn: ({ pageParam }) => api.search(q, { sort, seed, offset: pageParam, limit: PAGE, with_facets: pageParam === 0 }),
    initialPageParam: 0,
    getNextPageParam: (last, pages) => (last.has_more ? pages.length * PAGE : undefined),
    placeholderData: (prev) => prev,
  });
  const first = results.data?.pages[0];
  const photos = results.data?.pages.flatMap((p) => p.photos) ?? [];
  const facets = first?.facets;
  const set = (patch: Partial<ThemeQuery>) => setQuery((cur) => ({ ...cur, ...patch }));
  const dirty = theme.data && JSON.stringify(compact(theme.data.query)) !== JSON.stringify(q);

  return (
    <div className="search-layout">
      <details className="filters" open={wide}>
        <summary>Filters</summary>
        <label className="field">
          <span>Words</span>
          <input type="search" placeholder="e.g. eldora | campfire" value={text} onChange={(e) => setText(e.target.value)} />
          <small className="muted">Event names, AI captions and tags. All words must match; <code>|</code> separates alternatives.</small>
        </label>

        <div className="field">
          <span>Years</span>
          <div className="row">
            <select value={query.year_from ?? ""} onChange={(e) => set({ year_from: e.target.value ? Number(e.target.value) : null })}>
              <option value="">Any</option>
              {YEARS.map((y) => <option key={y}>{y}</option>)}
            </select>
            –
            <select value={query.year_to ?? ""} onChange={(e) => set({ year_to: e.target.value ? Number(e.target.value) : null })}>
              <option value="">Any</option>
              {YEARS.map((y) => <option key={y}>{y}</option>)}
            </select>
          </div>
        </div>

        <div className="field">
          <span>Season / month</span>
          <div className="chips">
            {SEASONS.map(([name, months]) => {
              const on = months.every((m) => query.months?.includes(m));
              return (
                <button key={name} className={`chip ${on ? "on" : ""}`} onClick={() =>
                  set({ months: on ? query.months?.filter((m) => !months.includes(m)) : [...new Set([...(query.months ?? []), ...months])] })}>
                  {name}
                </button>
              );
            })}
          </div>
          <Chips facets={facets?.month} selected={query.months} label={(m) => MONTHS[Number(m) - 1]} numeric
            onToggle={(m) => set({ months: toggle(query.months, Number(m)) })} />
        </div>

        <div className="field">
          <span>Where</span>
          <Chips facets={facets?.state} selected={query.states} label={(s) => (s === "abroad" ? "Abroad" : String(s))}
            onToggle={(s) => set({ states: toggle(query.states, String(s)) })} />
          {(facets?.country?.length ?? 0) > 1 && (
            <Chips facets={facets?.country} selected={query.countries}
              onToggle={(c) => set({ countries: toggle(query.countries, String(c)) })} />
          )}
          <details>
            <summary className="small muted">State / region</summary>
            <Chips facets={facets?.region?.slice(0, 30)} selected={query.regions}
              onToggle={(r) => set({ regions: toggle(query.regions, String(r)) })} />
          </details>
        </div>

        {TAG_CATEGORIES.some((c) => facets?.[c]?.length || query.tags?.some((t) => t.startsWith(c + ":"))) && (
          <div className="field">
            <span>What (AI tags)</span>
            {TAG_CATEGORIES.map((c) => (facets?.[c]?.length || query.tags?.some((t) => t.startsWith(c + ":"))) ? (
              <div key={c} className="tag-facet">
                <small className="muted">{CATEGORY_LABEL[c]}</small>
                <TagChips facets={facets?.[c]} selected={query.tags?.filter((t) => t.startsWith(c + ":"))}
                  onToggle={(t) => set({ tags: toggle(query.tags, t) })} />
              </div>
            ) : null)}
            <small className="muted">Within a group, any tag matches; across groups, all must.</small>
          </div>
        )}

        {(facets?.score?.length ?? 0) > 0 && (
          <div className="field">
            <span>Quality (AI score)</span>
            <select value={query.min_score ?? ""} onChange={(e) => set({ min_score: e.target.value ? Number(e.target.value) : null })}>
              <option value="">Any</option>
              {[6, 7, 8, 9].map((n) => (
                <option key={n} value={n}>
                  {n}+ ({(facets?.score ?? []).filter((f) => Number(f.value) >= n).reduce((a, f) => a + f.count, 0).toLocaleString()})
                </option>
              ))}
            </select>
          </div>
        )}

        <div className="field">
          <span>With</span>
          <Chips facets={facets?.person?.slice(0, 30)} selected={query.people}
            label={(id) => facets?.person?.find((f) => f.value === id)?.label ?? people.data?.find((p) => p.id === id)?.name ?? `#${id}`}
            onToggle={(id) => set({ people: toggle(query.people, Number(id)) })} />
          {(query.people?.length ?? 0) > 1 && (
            <div className="row small">
              <label className="check"><input type="radio" checked={!query.people_all} onChange={() => set({ people_all: false })} /> any of them</label>
              <label className="check"><input type="radio" checked={!!query.people_all} onChange={() => set({ people_all: true })} /> all together</label>
            </div>
          )}
          <select value={query.group ?? ""} onChange={(e) => set({ group: (e.target.value || null) as ThemeQuery["group"] })}>
            <option value="">Any number of people</option>
            <option value="solo">Just one person</option>
            <option value="small">2–4 people</option>
            <option value="large">5 or more</option>
          </select>
        </div>

        <div className="field">
          <span>Camera</span>
          <Chips facets={facets?.camera?.slice(0, 12)} selected={query.cameras}
            onToggle={(c) => set({ cameras: toggle(query.cameras, String(c)) })} />
        </div>

        <div className="field">
          <label className="check"><input type="checkbox" checked={!!query.highlights_only}
            onChange={(e) => set({ highlights_only: e.target.checked })} /> Highlights only</label>
          <label className="check"><input type="checkbox" checked={query.has_gps === true}
            onChange={(e) => set({ has_gps: e.target.checked ? true : null })} /> Has GPS</label>
          <label className="check"><input type="checkbox" checked={query.collapse_bursts !== false}
            onChange={(e) => set({ collapse_bursts: e.target.checked })} /> One shot per burst</label>
        </div>

        <button className="link" onClick={() => { setQuery({}); setText(""); }}>Clear filters</button>
      </details>

      <section className="results">
        <div className="results-header">
          <div>
            <h1>{theme.data ? theme.data.name : "Search"}{dirty && <span className="muted"> (edited)</span>}</h1>
            <p className="muted">
              {first?.total != null ? `${first.total.toLocaleString()} photos` : "…"}
              {" · "}searching highlights and folders you've added to processing
            </p>
          </div>
          <div className="actions">
            <select value={sort} onChange={(e) => setSort(e.target.value as Sort)}>
              {(Object.keys(SORT_LABEL) as Sort[]).map((s) => <option key={s} value={s}>{SORT_LABEL[s]}</option>)}
            </select>
            <Link className={`button primary ${photos.length ? "" : "disabled"}`} to={`/play?${queryParams(q, sort)}`}>▶ Play</Link>
            <SaveTheme query={q} sort={sort} theme={theme.data} />
          </div>
        </div>
        {results.error && <p className="error">{String(results.error)}</p>}
        {results.isLoading ? <p className="muted">Searching…</p> : photos.length === 0 ? (
          <p className="muted">No photos match.</p>
        ) : (
          <>
            <PhotoTiles photos={photos} onOpen={setOpen} />
            {results.hasNextPage && (
              <button className="more" onClick={() => results.fetchNextPage()} disabled={results.isFetchingNextPage}>
                {results.isFetchingNextPage ? "Loading…" : "Load more"}
              </button>
            )}
          </>
        )}
        {open != null && <Lightbox photos={photos} index={open} onClose={() => setOpen(null)} onMove={setOpen} />}
      </section>
    </div>
  );
}
