export type Counts = { photos: number; processing: number; thumbs: number; highlights: number; issues: number };

export type Issue = { code: string; severity: "error" | "warning"; message: string };

export type Folder = {
  id: number;
  name: string;
  path: string;
  kind: string | null;
  year: number | null;
  event_date: string | null;
  state: string | null;
  event_name: string | null;
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
};

export type FolderDetail = { folder: Folder; children: Folder[]; breadcrumbs: { id: number; name: string }[] };
export type PhotoPage = { photos: Photo[]; has_more: boolean };
export type Stats = Record<string, number>;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...init });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${path}`);
  return res.json() as Promise<T>;
}

export const api = {
  stats: () => request<Stats>("/api/stats"),
  tree: () => request<Folder[]>("/api/tree"),
  folder: (id: number) => request<FolderDetail>(`/api/folders/${id}`),
  photos: (id: number, offset: number) => request<PhotoPage>(`/api/folders/${id}/photos?offset=${offset}&limit=200`),
  issues: () => request<Folder[]>("/api/issues"),
  setScope: (id: number, inScope: boolean) =>
    request<Folder>(`/api/folders/${id}/scope`, { method: "PUT", body: JSON.stringify({ in_scope: inScope }) }),
  originalUrl: (id: number) => `/api/photos/${id}/original`,
};
