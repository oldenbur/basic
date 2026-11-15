"""Keep face labels up to date: match faces to the people you've confirmed, and regroup the rest."""

import logging
import threading
from collections import Counter

import numpy as np
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from photoindex.faces.cluster import AUTO_ASSIGN, SUGGEST, cluster, match
from photoindex.models import Face

log = logging.getLogger(__name__)


def _stack(rows) -> np.ndarray:
    return np.vstack([np.asarray(r.embedding, dtype=np.float32) for r in rows]) if rows else np.zeros((0, 512), np.float32)


def refresh_matches(session: Session) -> Counter:
    """Re-match every face you haven't labelled yourself against the faces you have.

    Only your own labels are used as references, never automatic ones, so a wrong automatic match can't
    pull more faces after it. Auto labels and suggestions are recomputed from scratch each time, so removing
    or moving a face you labelled takes back anything that was matched because of it.
    """
    refs = session.execute(
        select(Face.embedding, Face.person_id)
        .where(Face.assigned_by == "user", Face.person_id.is_not(None), ~Face.ignored)
    ).all()
    cands = session.execute(
        select(Face.id, Face.embedding, Face.person_id, Face.assigned_by, Face.suggested_person_id,
               Face.suggested_score, Face.rejected_person_ids, Face.cluster_id)
        .where(Face.assigned_by.is_distinct_from("user"), ~Face.ignored)
    ).all()
    stats: Counter = Counter()
    if not cands:
        return stats
    matches = match(_stack(cands), _stack(refs), np.array([r.person_id for r in refs]),
                    [set(c.rejected_person_ids or ()) for c in cands])
    changes = []
    for c, m in zip(cands, matches, strict=True):
        new = dict(person_id=None, assigned_by=None, suggested_person_id=None, suggested_score=None,
                   cluster_id=c.cluster_id)
        if m.person_id is not None and m.score >= AUTO_ASSIGN:
            new.update(person_id=m.person_id, assigned_by="auto", cluster_id=None)
            stats["auto"] += 1
        elif m.person_id is not None and m.score >= SUGGEST:
            new.update(suggested_person_id=m.person_id, suggested_score=round(m.score, 4))
            stats["suggested"] += 1
        old = dict(person_id=c.person_id, assigned_by=c.assigned_by, suggested_person_id=c.suggested_person_id,
                   suggested_score=c.suggested_score, cluster_id=c.cluster_id)
        if new != old:
            changes.append(dict(id=c.id, **new))
    for i in range(0, len(changes), 2000):
        session.execute(update(Face), changes[i : i + 2000])
    session.commit()
    stats["changed"] = len(changes)
    return stats


def recluster(session: Session) -> Counter:
    """Group the faces that have no person yet. A group's id is its smallest face id."""
    rows = session.execute(
        select(Face.id, Face.embedding, Face.cluster_id).where(Face.person_id.is_(None), ~Face.ignored)
        .order_by(Face.id)
    ).all()
    labels = cluster(_stack(rows)) if rows else np.array([], dtype=int)
    first: dict[int, int] = {}
    for r, label in zip(rows, labels, strict=True):
        if label >= 0:
            first.setdefault(int(label), r.id)
    changes = []
    for r, label in zip(rows, labels, strict=True):
        cid = first[int(label)] if label >= 0 else None
        if cid != r.cluster_id:
            changes.append(dict(id=r.id, cluster_id=cid))
    for i in range(0, len(changes), 2000):
        session.execute(update(Face), changes[i : i + 2000])
    session.commit()
    return Counter(groups=len(first), grouped=sum(1 for x in labels if x >= 0), ungrouped=sum(1 for x in labels if x < 0))


def refresh(session: Session) -> dict:
    return dict(matches=dict(refresh_matches(session)), clusters=dict(recluster(session)))


class _Refresher:
    """Runs refresh_matches in the background after edits in the UI, coalescing bursts of clicks into one run."""

    def __init__(self):
        self._wanted = threading.Event()
        self._regroup = False
        self._idle = threading.Event()
        self._idle.set()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def request(self, regroup: bool = False) -> None:
        """Re-match soon; with regroup, also re-cluster the unnamed faces (can take a minute)."""
        with self._lock:
            self._regroup = self._regroup or regroup
            self._wanted.set()
            self._idle.clear()
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._run, name="people-refresh", daemon=True)
                self._thread.start()

    @property
    def busy(self) -> bool:
        return not self._idle.is_set()

    def wait(self, timeout: float = 120) -> bool:
        """Block until no refresh is pending (tests, and API calls that must read fresh results)."""
        return self._idle.wait(timeout)

    def _run(self) -> None:
        from photoindex.db import session_factory

        while True:
            with self._lock:
                if not self._wanted.is_set():
                    self._idle.set()
                    self._thread = None
                    return
                self._wanted.clear()
                regroup, self._regroup = self._regroup, False
            try:
                with session_factory()() as session:
                    log.info("people refresh: %s", dict(refresh_matches(session)))
                    if regroup:
                        log.info("people regroup: %s", dict(recluster(session)))
            except Exception:
                log.exception("people refresh failed")


refresher = _Refresher()
