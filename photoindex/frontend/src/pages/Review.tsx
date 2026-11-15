import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { FaceCrop, useFaceRefresh } from "../components/People";

/** One uncertain match at a time: Y / N / S on the keyboard. */
export function Review() {
  const qc = useQueryClient();
  const refresh = useFaceRefresh();
  const q = useQuery({ queryKey: ["review"], queryFn: api.review, staleTime: Infinity });
  const [done, setDone] = useState<Set<number>>(new Set()); // answered or skipped in this session
  const [count, setCount] = useState(0);
  const queue = (q.data?.faces ?? []).filter((f) => !done.has(f.id));
  const current = queue[0];

  const answer = useMutation({
    mutationFn: ({ id, accept }: { id: number; accept: boolean }) => api.reviewFace(id, accept),
    onSuccess: () => {
      setCount((c) => c + 1);
      qc.invalidateQueries({ queryKey: ["faceStats"] });
    },
  });
  const act = (accept: boolean | null) => {
    if (!current) return;
    if (accept !== null) answer.mutate({ id: current.id, accept });
    setDone((s) => new Set(s).add(current.id));
  };

  // Fetch the next batch when this one runs low. Wait a moment first: each answer re-matches the remaining
  // faces in the background, which changes what's worth asking next. Only refetch after new answers, so a
  // queue of skipped faces doesn't poll forever.
  const [answeredAtFetch, setAnsweredAtFetch] = useState(0);
  useEffect(() => {
    if (queue.length < 3 && !q.isFetching && count > answeredAtFetch) {
      const t = setTimeout(() => { setAnsweredAtFetch(count); q.refetch(); refresh(); }, 1200);
      return () => clearTimeout(t);
    }
  }, [queue.length, q, count, answeredAtFetch, refresh]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "y" || e.key === "ArrowRight") act(true);
      else if (e.key === "n" || e.key === "ArrowLeft") act(false);
      else if (e.key === "s" || e.key === " ") { e.preventDefault(); act(null); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  return (
    <>
      <div className="crumbs"><Link to="/people">People</Link></div>
      <h1>Review suggestions</h1>
      <p className="muted">
        {q.data ? `${q.data.total.toLocaleString()} waiting` : "…"}{count > 0 && ` · ${count} answered`}
        {" · "}these look like someone you've named, but not certainly enough to label automatically.
      </p>
      {q.isLoading ? <p className="muted">Loading…</p> : !current ? (
        <p className="muted">{q.isFetching ? "Loading more…" : "Nothing to review. Name more groups on the People page to get suggestions."}</p>
      ) : (
        <div className="review">
          <div className="review-face">
            <FaceCrop face={current} size={220} />
            {current.photo_thumb_url && <img className="review-context" src={current.photo_thumb_url} alt="" />}
          </div>
          <div className="review-question">
            <h2>Is this <strong>{current.suggested_name}</strong>?</h2>
            <div className="review-examples">
              {current.examples.map((e) => <FaceCrop key={e.id} face={e} size={88} title={`${current.suggested_name} (confirmed)`} />)}
            </div>
            <p className="muted small">match {Math.round((current.suggested_score ?? 0) * 100)}%</p>
            <div className="actions">
              <button className="primary" onClick={() => act(true)}>Yes <kbd>Y</kbd></button>
              <button onClick={() => act(false)}>No <kbd>N</kbd></button>
              <button className="link" onClick={() => act(null)}>Skip <kbd>S</kbd></button>
            </div>
            {answer.error && <p className="error small">{String(answer.error)}</p>}
          </div>
        </div>
      )}
    </>
  );
}
