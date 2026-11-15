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
  face_count: number | null;
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
  people?: number[];
  people_all?: boolean;
  group?: "solo" | "small" | "large" | null;
};

export type Sort = "event_shuffle" | "date" | "shuffle";
export const SORT_LABEL: Record<Sort, string> = {
  event_shuffle: "Events shuffled, in order within each",
  date: "Oldest first",
  shuffle: "Fully shuffled",
};

export type Facet = { value: string | number; count: number; label?: string };
export type SearchResult = {
  photos: Photo[];
  has_more: boolean;
  total?: number;
  facets?: Record<"year" | "month" | "state" | "camera" | "person", Facet[]>;
};

export type Face = {
  id: number;
  photo_id: number;
  box: [number, number, number, number]; // x, y, w, h as fractions of the display image
  size_px: number;
  quality: number;
  crop_url: string | null;
  person_id: number | null;
  person_name: string | null;
  assigned_by: "user" | "auto" | null;
  cluster_id: number | null;
  ignored: boolean;
  suggested_person_id: number | null;
  suggested_name: string | null;
  suggested_score: number | null;
};
export type Person = { id: number; name: string; faces: number; photos: number; cover_face_id: number | null; cover_url: string | null };
export type Cluster = { cluster_id: number; size: number; faces: Face[] };
export type ClusterPage = { clusters: Cluster[]; has_more: boolean; groups: number; ungrouped: number };
export type ReviewItem = Face & { examples: Face[]; photo_thumb_url: string | null };
export type FaceStats = {
  faces: number; named_by_you: number; named_auto: number; to_review: number; unnamed: number; ignored: number;
  people: number; updating: boolean;
};
export type FaceUpdate = { person_id?: number; name?: string; clear?: boolean; ignored?: boolean };

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

  people: () => request<Person[]>("/api/people"),
  person: (id: number) => request<Person>(`/api/people/${id}`),
  renamePerson: (id: number, name: string, cover_face_id: number | null) =>
    post<Person>(`/api/people/${id}`, { name, cover_face_id }, "PUT"),
  deletePerson: (id: number) => request<void>(`/api/people/${id}`, { method: "DELETE" }),
  mergePerson: (id: number, into_id: number) => post<Person>(`/api/people/${id}/merge`, { into_id }),
  personFaces: (id: number, offset: number) =>
    request<{ faces: Face[]; has_more: boolean }>(`/api/people/${id}/faces?offset=${offset}&limit=200`),
  clusters: (offset: number) => request<ClusterPage>(`/api/clusters?offset=${offset}&limit=20`),
  clusterFaces: (id: number) => request<Face[]>(`/api/clusters/${id}/faces`),
  assignCluster: (id: number, who: { person_id?: number; name?: string }, exclude_face_ids: number[]) =>
    post<Person>(`/api/clusters/${id}/assign`, { ...who, exclude_face_ids }),
  ignoreCluster: (id: number, exclude_face_ids: number[]) =>
    post<{ ignored: number }>(`/api/clusters/${id}/ignore`, { exclude_face_ids }),
  regroup: () => post<{ started: boolean }>("/api/clusters/regroup", {}),
  photoFaces: (photoId: number) => request<Face[]>(`/api/photos/${photoId}/faces`),
  updateFace: (id: number, body: FaceUpdate) => post<Face>(`/api/faces/${id}`, body, "PATCH"),
  review: () => request<{ faces: ReviewItem[]; total: number }>("/api/review?limit=20"),
  reviewFace: (id: number, accept: boolean) => post<{ ok: boolean }>(`/api/faces/${id}/review`, { accept }),
  faceStats: () => request<FaceStats>("/api/faces/stats"),
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
