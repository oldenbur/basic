export type Counts = {
  photos: number; processing: number; thumbs: number; highlights: number; linked: number; ignored: number; issues: number;
};

export type Issue = { code: string; severity: "warning" | "ignored"; message: string };

export type Folder = {
  id: number;
  name: string;
  path: string;
  kind: string | null;
  year: number | null;
  event_date: string | null;
  state: string | null;
  event_name: string | null;
  abroad: boolean;
  parse_ok: boolean | null;
  issues: Issue[];
  suggested_name: string | null;
  in_scope: boolean;
  counts: Counts;
};

export type Photo = {
  id: number;
  name: string;
  path: string;
  taken_at: string | null;
  camera: string | null;
  lat: number | null;
  lon: number | null;
  is_highlight_copy: boolean;
  original_id: number | null;
  link_method: string | null;
  has_highlight: boolean;
  in_processing_set: boolean;
  burst_group_id: number | null;
  date_mismatch_days: number | null;
  thumb_status: string;
  thumb_url: string | null;
  display_url: string;
  // present on search results
  event_name?: string;
  event_folder_id?: number;
  event_date?: string | null;
  state?: string | null;
  abroad?: boolean;
};

export type ThemeQuery = {
  text?: string;
  year_from?: number | null;
  year_to?: number | null;
  months?: number[];
  states?: string[];
  cameras?: string[];
  folder_ids?: number[];
  has_gps?: boolean | null;
  highlights_only?: boolean;
  collapse_bursts?: boolean;
};

export type Sort = "event_shuffle" | "date" | "shuffle";
export const SORT_LABEL: Record<Sort, string> = {
  event_shuffle: "Events shuffled, in order within each",
  date: "Oldest first",
  shuffle: "Fully shuffled",
};

export type Facet = { value: string | number; count: number };
export type SearchResult = {
  photos: Photo[];
  has_more: boolean;
  total?: number;
  facets?: Record<"year" | "month" | "state" | "camera", Facet[]>;
};

export type Theme = {
  id: number;
  name: string;
  query: ThemeQuery;
  sort: Sort;
  cover_photo_id: number | null;
  cover_url: string | null;
  count: number;
  preparing: boolean;
  prepared?: number;
};

export type FolderDetail = { folder: Folder; children: Folder[]; breadcrumbs: { id: number; name: string }[] };
export type PhotoPage = { photos: Photo[]; has_more: boolean };
export type Stats = Record<string, number>;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...init });
  if (!res.ok) {
    const detail = await res.json().then((j) => j.detail, () => null);
    throw new Error(typeof detail === "string" ? detail : `${res.status} ${res.statusText}: ${path}`);
  }
  return (res.status === 204 ? undefined : res.json()) as Promise<T>;
}

const post = <T>(path: string, body: unknown, method = "POST") =>
  request<T>(path, { method, body: JSON.stringify(body) });

export type ThemeIn = { name: string; query: ThemeQuery; sort: Sort; cover_photo_id?: number | null };

export const api = {
  stats: () => request<Stats>("/api/stats"),
  tree: () => request<Folder[]>("/api/tree"),
  folder: (id: number) => request<FolderDetail>(`/api/folders/${id}`),
  photos: (id: number, offset: number) => request<PhotoPage>(`/api/folders/${id}/photos?offset=${offset}&limit=200`),
  issues: () => request<Folder[]>("/api/issues"),
  setScope: (id: number, inScope: boolean) =>
    request<Folder>(`/api/folders/${id}/scope`, { method: "PUT", body: JSON.stringify({ in_scope: inScope }) }),
  originalUrl: (id: number) => `/api/photos/${id}/original`,
  search: (query: ThemeQuery, opts: { sort?: Sort; seed?: number; offset?: number; limit?: number; with_facets?: boolean }) =>
    post<SearchResult>("/api/search", { query, ...opts }),
  onThisDay: (d: Date) => request<Photo[]>(`/api/onthisday?month=${d.getMonth() + 1}&day=${d.getDate()}`),
  themes: () => request<Theme[]>("/api/themes"),
  theme: (id: number) => request<Theme>(`/api/themes/${id}`),
  createTheme: (t: ThemeIn) => post<Theme>("/api/themes", t),
  updateTheme: (id: number, t: ThemeIn) => post<Theme>(`/api/themes/${id}`, t, "PUT"),
  deleteTheme: (id: number) => request<void>(`/api/themes/${id}`, { method: "DELETE" }),
  prepareTheme: (id: number) => post<{ photos: number }>(`/api/themes/${id}/prepare`, {}),
};

/** "OldenburgWinterPark" -> "Oldenburg Winter Park", "MooseRiverBWCA" -> "Moose River BWCA". */
export function eventTitle(name: string): string {
  return name.replace(/([a-z])([A-Z0-9])/g, "$1 $2").replace(/([A-Z]+)([A-Z][a-z])/g, "$1 $2").replace(/_/g, " ");
}

/** Query string form used by /search and /play links: ?q=<json>&sort=... or ?theme=<id>. */
export function queryParams(query: ThemeQuery, sort?: Sort): string {
  const p = new URLSearchParams({ q: JSON.stringify(query) });
  if (sort) p.set("sort", sort);
  return p.toString();
}
