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
  caption: string | null;
  aesthetic: number | null;
  rotation: number;
  place: string | null;
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
  tags?: string[]; // "category:value"
  countries?: string[];
  regions?: string[];
  min_score?: number | null;
};

export type Sort = "event_shuffle" | "date" | "shuffle" | "best";
export const SORT_LABEL: Record<Sort, string> = {
  event_shuffle: "Events shuffled, in order within each",
  date: "Oldest first",
  shuffle: "Fully shuffled",
  best: "Best first (AI score)",
};

export const TAG_CATEGORIES = ["activity", "scene", "object", "animal", "gear", "vehicle", "landmark"] as const;
export type TagCategory = (typeof TAG_CATEGORIES)[number];
export const CATEGORY_LABEL: Record<TagCategory, string> = {
  activity: "Doing", scene: "Scene", object: "Things", animal: "Animals", gear: "Camping gear",
  vehicle: "Vehicles", landmark: "Landmarks",
};

export type Facet = { value: string | number; count: number; label?: string };
export type SearchResult = {
  photos: Photo[];
  has_more: boolean;
  total?: number;
  facets?: Record<"year" | "month" | "state" | "camera" | "person" | "country" | "region" | "score" | TagCategory, Facet[]>;
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

export type ModelInfo = {
  id: string; label: string; per_photo: number | null; measured: boolean; estimate_all: number; estimate_remaining: number;
};
export type TagRun = {
  id: number; kind: "pilot" | "backfill"; model: string; batch_id: string; status: string; requests: number;
  succeeded: number; errored: number; est_cost_usd: number; cost_usd: number | null; created_at: string | null;
  ended_at: string | null;
};
export type TaggingStatus = {
  config: { model: string | null; daily_cap: number; paused: boolean };
  state: "not_started" | "pilot" | "running" | "waiting_cap" | "paused" | "done";
  spent_today: number;
  total_cost: number;
  tagged: number;
  counts: Record<string, number>;
  models: ModelInfo[];
  has_key: boolean;
  runs: TagRun[];
  pilot_starting: boolean;
  pilot_error: string | null;
  worker_error: string | null;
};
export type Location = { country: string; region: string; city: string; place_name: string; confidence: string };
export type PilotAnswer = {
  id: number; model: string; label: string; status: string; error: string | null; caption: string | null;
  aesthetic: number | null; rotation: number | null; confidence: string | null; location: Location | null;
  people_count: number | null; setting: string | null; vehicles: { type: string; make_model: string; color: string }[];
  tags: string[]; cost_usd: number | null; output_tokens: number | null; best: boolean; flags: string[];
};
export type PilotPhoto = { photo_id: number; name: string; thumb_url: string | null; display_url: string; answers: PilotAnswer[]; voted: boolean };
export type PilotModel = {
  model: string; label: string; answers: number; done: number; best: number; flagged: number; flags: number;
  cost: number; rotations: number; per_photo: number | null; estimate_all: number | null; avg_output_tokens: number | null;
};
export type Pilot = { photos: PilotPhoto[]; models: PilotModel[]; highlights: number; voted: number; running: number; runs: number };
export type TagItem = { id: number; category: TagCategory; value: string; key: string; count: number; hidden: boolean };
export type PhotoAI = {
  photo_id: number; caption: string | null; scene: string | null; setting: string | null; aesthetic: number | null;
  rotation: number; tag_status: string;
  place: { country: string | null; region: string | null; city: string | null; source: string | null };
  place_name: string | null; model: string | null;
  tags: { id: number; category: TagCategory; value: string; key: string; source: string }[];
  removed: { id: number; category: TagCategory; value: string }[];
};

export type AlbumEvent = {
  id: number; seq: number; size: number; first_name: string; last_name: string; break_reasons: string[];
  break_score: number | null; has_me: boolean; people: { id: number; name: string; count: number }[];
  photos: { id: number; name: string; faces: number | null; thumb_url: string | null }[];
};
export type Albums = {
  albums: { album: string; prints: number; faces_done: number; events: number; events_with_me: number }[];
  album: string | null; faces: number; events: AlbumEvent[];
};

export type RefKind = "home" | "family" | "school" | "event" | "trip" | "other";
export type RefExample = { photo_id: number; name: string; album: string; status: "proposed" | "confirmed" | "rejected"; source: string; thumb_url: string | null };
export type AlbumRef = { id: number; kind: RefKind; label: string; notes: string | null; start: string | null; end: string | null; examples: RefExample[] };
export type RefIn = { kind?: RefKind; label?: string; start?: string | null; end?: string | null; notes?: string | null };
export type FaceGroup = {
  id: number; size: number; guess_id: number | null; guess_name: string | null; guess_count: number;
  first: string; last: string; albums: string[];
  faces: { id: number; photo_id: number; crop_url: string | null; where: string }[];
};
export type FaceGroups = {
  total: number; groups: FaceGroup[]; named: { id: number; name: string; count: number }[];
  people: { id: number; name: string }[];
};

export type DateRun = {
  id: number; kind: "pilot" | "full"; model: string; status: string; requests: number; succeeded: number; errored: number;
  est_cost_usd: number; cost_usd: number | null; created_at: string | null;
};
export type DatingStatus = { runs: DateRun[]; dated: number; prints: number; has_key: boolean; pilot_max_usd: number };
export type DatingEstimate = { events: number; prints: number; low: number; high: number };
export type PrintDate = {
  photo_id: number; name: string; thumb_url: string | null; best?: string | null; earliest?: string | null;
  latest?: string | null; confidence?: string | null; reference?: string | null; ages?: { name: string; age: number }[];
  different_occasion?: boolean; caption?: string | null;
};
export type DatedEvent = {
  id: number; album: string; seq: number; status: string; error: string | null; cost_usd: number | null;
  summary: string | null; best: string | null; earliest: string | null; latest: string | null;
  confidence: string | null; clues: string | null; prints: PrintDate[];
};

export type PlacementYear = { year: number; include?: number; older?: number; review?: number; skip?: number };
export type PlacedPrint = { photo_id: number; name: string; month: string; status: string; source: string; thumb_url: string | null };
export type PlacedEvent = {
  key: string; album: string; label: string; summary: string | null; has_me: boolean; month: string; first: string; last: string;
  your_month: string | null; decision: "include" | "skip" | "undecided" | null; waits: boolean;
  prev: string | null; next: string | null; prints: PlacedPrint[];
};
export type Placements = { years: PlacementYear[]; events: PlacedEvent[] };

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

  albums: (album?: string) => request<Albums>(`/api/albums${album ? `?album=${encodeURIComponent(album)}` : ""}`),
  albumRefs: () => request<AlbumRef[]>("/api/albums/refs"),
  createRef: (body: RefIn) => post<AlbumRef>("/api/albums/refs", body),
  editRef: (id: number, body: RefIn) => post<{ ok: boolean }>(`/api/albums/refs/${id}`, body, "PATCH"),
  deleteRef: (id: number) => request<void>(`/api/albums/refs/${id}`, { method: "DELETE" }),
  setExample: (refId: number, photoId: number, status: RefExample["status"]) =>
    post<{ ok: boolean }>(`/api/albums/refs/${refId}/examples/${photoId}`, { status }, "PUT"),
  removeExample: (refId: number, photoId: number) =>
    request<void>(`/api/albums/refs/${refId}/examples/${photoId}`, { method: "DELETE" }),
  faceGroups: (offset: number) => request<FaceGroups>(`/api/albums/face-groups?offset=${offset}&limit=10`),
  faceGroupFaces: (id: number) => request<FaceGroup["faces"]>(`/api/albums/face-groups/${id}/faces`),
  nameFaceGroup: (id: number, who: { person_id?: number; name?: string }, exclude_face_ids: number[]) =>
    post<{ named: number; person_id: number }>(`/api/albums/face-groups/${id}/assign`, { ...who, exclude_face_ids }),
  ignoreFaceGroup: (id: number, exclude_face_ids: number[]) =>
    post<{ ignored: number }>(`/api/albums/face-groups/${id}/ignore`, { exclude_face_ids }),
  dating: () => request<DatingStatus>("/api/albums/dating"),
  datingEstimate: (kind: "pilot" | "rest") => request<DatingEstimate>(`/api/albums/dating/estimate?kind=${kind}`),
  startDatingPilot: (max_usd: number) => post<DateRun>("/api/albums/dating/pilot", { max_usd }),
  pollDating: () => post<Record<string, number>>("/api/albums/dating/poll", {}),
  datingResults: () => request<DatedEvent[]>("/api/albums/dating/results"),
  placements: (view: "review" | "all", year?: number) =>
    request<Placements>(`/api/albums/placements?view=${view}${year ? `&year=${year}` : ""}`),
  runPlacement: () => post<Record<string, number>>("/api/albums/placements/run", {}),
  movePrints: (photo_ids: number[], to: string) => post<{ to: string; moved: number }>("/api/albums/placements/move", { photo_ids, to }),
  editEvent: (key: string, edit: { status?: "include" | "skip" | "auto"; month?: string }) =>
    post<{ key: string }>(`/api/albums/placements/events/${key}`, edit, "PUT"),
  regroupAlbumFaces: () => post<Record<string, number>>("/api/albums/face-groups/regroup", {}),

  tagging: () => request<TaggingStatus>("/api/tagging"),
  taggingSettings: (body: { daily_cap?: number; paused?: boolean }) => post<TaggingStatus["config"]>("/api/tagging/settings", body, "PUT"),
  startPilot: (size: number) => post<{ starting: boolean; estimate?: number }>("/api/tagging/pilot", { size }),
  pilot: () => request<Pilot>("/api/tagging/pilot"),
  vote: (photoId: number, best_id: number | null, flags: Record<number, string[]>) =>
    post<{ ok: boolean }>(`/api/tagging/pilot/${photoId}/vote`, { best_id, flags }),
  chooseModel: (model: string) => post<{ model: string; applied: number }>("/api/tagging/choose", { model }),
  pollTagging: () => post<{ ok: boolean }>("/api/tagging/poll", {}),
  tags: () => request<TagItem[]>("/api/tags"),
  editTag: (id: number, body: { value?: string; hidden?: boolean; merge_into_id?: number }) =>
    post<TagItem>(`/api/tags/${id}`, body, "PATCH"),
  photoAI: (photoId: number) => request<PhotoAI>(`/api/photos/${photoId}/ai`),
  editPhotoTags: (photoId: number, body: { add?: string[]; remove?: number[] }) =>
    post<PhotoAI>(`/api/photos/${photoId}/tags`, body, "PATCH"),
  rotate: (photoId: number, rotation: number) =>
    post<{ rotation: number; thumb_url: string | null }>(`/api/photos/${photoId}/rotation`, { rotation }, "PUT"),
};

export const usd = (n: number | null | undefined, digits = 2) =>
  n == null ? "–" : `$${n.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;

/** "activity:skiing" -> "skiing" */
export const tagLabel = (key: string) => key.slice(key.indexOf(":") + 1);

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
