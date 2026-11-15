import { useInfiniteQuery, useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, Cluster, Face } from "../api";
import { FaceCrop, PersonPicker, useFaceRefresh, usePeople, Who } from "../components/People";

function ClusterCard({ cluster }: { cluster: Cluster }) {
  const people = usePeople();
  const refresh = useFaceRefresh();
  const [excluded, setExcluded] = useState<Set<number>>(new Set());
  const [showAll, setShowAll] = useState(false);
  const all = useQuery({
    queryKey: ["clusters", "faces", cluster.cluster_id],
    queryFn: () => api.clusterFaces(cluster.cluster_id),
    enabled: showAll,
  });
  const faces: Face[] = showAll && all.data ? all.data : cluster.faces;
  const toggle = (id: number) => setExcluded((s) => {
    const n = new Set(s);
    if (n.has(id)) n.delete(id); else n.add(id);
    return n;
  });
  const assign = useMutation({
    mutationFn: (who: Who) => api.assignCluster(cluster.cluster_id, who, [...excluded]),
    onSuccess: refresh,
  });
  const ignore = useMutation({
    mutationFn: () => api.ignoreCluster(cluster.cluster_id, [...excluded]),
    onSuccess: refresh,
  });
  const n = cluster.size - excluded.size;
  return (
    <div className="cluster-card">
      <div className="cluster-faces">
        {faces.map((f) => (
          <FaceCrop key={f.id} face={f} onClick={() => toggle(f.id)} selected={excluded.has(f.id)}
            title={excluded.has(f.id) ? "Left out: not this person. Click to put back." : "Click if this isn't the same person"}
            badge={excluded.has(f.id) ? "✕" : undefined} />
        ))}
        {!showAll && cluster.size > cluster.faces.length && (
          <button className="face-more" onClick={() => setShowAll(true)}>+{cluster.size - cluster.faces.length}</button>
        )}
      </div>
      <div className="cluster-actions">
        <span className="muted">{n.toLocaleString()} face{n === 1 ? "" : "s"}{excluded.size > 0 && ` (${excluded.size} left out)`}</span>
        <PersonPicker people={people.data} onPick={(who) => assign.mutate(who)} busy={assign.isPending} />
        <button className="link" onClick={() => ignore.mutate()} disabled={ignore.isPending}
          title="Strangers, crowds, people you don't need to find: hide these faces">
          Not someone I need
        </button>
        {(assign.error || ignore.error) && <span className="error small">{String(assign.error ?? ignore.error)}</span>}
      </div>
    </div>
  );
}

export function People() {
  const people = usePeople();
  const refresh = useFaceRefresh();
  // Poll quickly while the server is re-matching/regrouping, then refresh everything once it's done.
  const stats = useQuery({
    queryKey: ["faceStats"], queryFn: api.faceStats,
    refetchInterval: (q) => (q.state.data?.updating ? 2000 : 15_000),
  });
  const [wasUpdating, setWasUpdating] = useState(false);
  useEffect(() => {
    const updating = !!stats.data?.updating;
    if (wasUpdating && !updating) refresh();
    setWasUpdating(updating);
  }, [stats.data?.updating, wasUpdating, refresh]);
  const clusters = useInfiniteQuery({
    queryKey: ["clusters"],
    queryFn: ({ pageParam }) => api.clusters(pageParam),
    initialPageParam: 0,
    getNextPageParam: (last, pages) => (last.has_more ? pages.length * 20 : undefined),
  });
  const regroup = useMutation({ mutationFn: api.regroup, onSuccess: () => stats.refetch() });
  const groups = clusters.data?.pages.flatMap((p) => p.clusters) ?? [];
  const first = clusters.data?.pages[0];
  const s = stats.data;

  return (
    <>
      <div className="folder-header">
        <div>
          <h1>People</h1>
          {s && (
            <p className="muted">
              {s.faces.toLocaleString()} faces in highlights · {(s.named_by_you + s.named_auto).toLocaleString()} named
              ({s.named_auto.toLocaleString()} automatically) · {s.unnamed.toLocaleString()} unnamed
            </p>
          )}
        </div>
        <div className="actions">
          {s && s.to_review > 0 && (
            <Link className="button primary" to="/people/review">Review {s.to_review.toLocaleString()} suggestions</Link>
          )}
          <button onClick={() => regroup.mutate()} disabled={regroup.isPending || s?.updating}
            title="Regroup the unnamed faces (the pipeline does this after finding new faces); can take a minute">
            {s?.updating ? "Updating…" : "Regroup"}
          </button>
        </div>
      </div>

      {people.data && people.data.length > 0 && (
        <div className="people">
          {people.data.map((p) => (
            <Link key={p.id} to={`/people/${p.id}`} className="person-card">
              {p.cover_url ? <img src={p.cover_url} alt="" loading="lazy" /> : <span className="no-thumb" />}
              <span className="person-name">{p.name}</span>
              <span className="muted small">{p.photos.toLocaleString()} photos</span>
            </Link>
          ))}
        </div>
      )}

      <h2>Unnamed groups {first && <span className="muted">· {first.groups.toLocaleString()} groups, {first.ungrouped.toLocaleString()} faces not in any group</span>}</h2>
      <p className="muted small">
        Each group is faces that look like the same person. Click any face that doesn't belong, then type a name.
        The same person often appears as several groups (kids at different ages): give them the same name.
      </p>
      {clusters.isLoading ? <p className="muted">Loading…</p>
        : groups.length === 0 ? <p className="muted">No unnamed groups. {s && s.faces === 0 && <>Run <code>photoindex stage faces</code> to find faces.</>}</p>
        : groups.map((c) => <ClusterCard key={c.cluster_id} cluster={c} />)}
      {clusters.hasNextPage && (
        <button className="more" onClick={() => clusters.fetchNextPage()} disabled={clusters.isFetchingNextPage}>
          {clusters.isFetchingNextPage ? "Loading…" : "More groups"}
        </button>
      )}
    </>
  );
}
