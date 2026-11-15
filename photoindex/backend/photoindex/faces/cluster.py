"""Group unnamed faces and match faces to named people. Pure numpy/sklearn on L2-normalised embeddings."""

from dataclasses import dataclass

import numpy as np

# Cosine similarity of ArcFace embeddings: the same person is usually 0.5-0.8, strangers under 0.25.
# Cautious on purpose: a wrong automatic label is more annoying than a review question.
AUTO_ASSIGN = 0.55  # at least this close to faces you confirmed -> labelled automatically
# at least this close -> asked about in the review queue. On a real library, suggestions at 0.38-0.45 were
# mostly other people in the same sunglasses and caps; 0.45-0.55 was about half right.
SUGGEST = 0.45
TOP_K = 3  # a face is compared with the mean of its K nearest confirmed faces of each person
CHUNK = 2000


@dataclass
class Match:
    person_id: int | None  # best person not previously rejected for this face
    score: float  # top-K mean similarity to that person (0 when there's none)


def match(faces: np.ndarray, refs: np.ndarray, ref_people: np.ndarray,
          rejected: list[set[int]] | None = None) -> list[Match]:
    """For each row of `faces`, the closest person among the confirmed `refs` (rows labelled by `ref_people`).

    Using the K nearest of a person's faces rather than their average copes with people whose face changes
    over the years (kids growing up): a toddler photo only has to look like the other toddler photos.
    """
    out: list[Match] = []
    if len(refs) == 0:
        return [Match(None, 0.0) for _ in range(len(faces))]
    people = np.unique(ref_people)
    cols = [np.where(ref_people == p)[0] for p in people]
    for start in range(0, len(faces), CHUNK):
        sims = faces[start : start + CHUNK] @ refs.T
        per_person = np.full((len(sims), len(people)), -1.0, dtype=np.float32)
        for j, c in enumerate(cols):
            k = min(TOP_K, len(c))
            s = sims[:, c]
            per_person[:, j] = np.partition(s, len(c) - k, axis=1)[:, -k:].mean(axis=1) if k < len(c) else s.mean(1)
        for i, row in enumerate(per_person):
            banned = rejected[start + i] if rejected else set()
            order = np.argsort(row)[::-1]
            best = next((j for j in order if int(people[j]) not in banned), None)
            out.append(Match(None, 0.0) if best is None else Match(int(people[best]), float(row[best])))
    return out


def cluster(embeddings: np.ndarray, min_size: int = 3) -> np.ndarray:
    """Group similar faces. Returns a label per row; -1 for faces that don't clearly belong to any group.

    HDBSCAN needs no guess of how many people there are and leaves ambiguous faces out instead of forcing
    them in. Measured on synthetic faces with realistic spread plus many one-off strangers: full 512-d
    embeddings with min_samples=5 gave ~99.7% pure groups and grouped no strangers; reducing to 64/128-d with
    PCA, or min_samples=2-3, grouped 3-40% of strangers into people.
    """
    from sklearn.cluster import HDBSCAN

    n = len(embeddings)
    if n < min_size:
        return np.full(n, -1)
    # brute force: all pairwise distances at once. ~8s for 20k faces vs ~70s with a tree in 512-d, but it
    # peaked at 6.6GB for 20k (n^2 float64 matrices), too much for a 16GB laptop; ~2.4GB at 12k.
    algorithm = "brute" if n <= 12_000 else "ball_tree"
    # min_samples=5 means a person needs ~5 faces before they form a group. In a small set (a new library)
    # that would leave almost everyone ungrouped, and strangers rarely collide anyway, so relax it there.
    min_samples = min(n, 3 if n < 200 else 5)
    labels = HDBSCAN(min_cluster_size=min_size, min_samples=min_samples, algorithm=algorithm, copy=True,
                     n_jobs=-1).fit_predict(embeddings.astype(np.float32))
    labels = _split_loose(embeddings, labels, min_size)
    return _drop_outliers(embeddings, labels, min_size)


# Average similarity of a group's faces to the group's average face. On a real library single-person groups
# scored 0.71-0.75; groups mixing people (siblings as kids, mostly) scored 0.61-0.66.
SPLIT_BELOW = 0.68


def _cohesion(e: np.ndarray) -> float:
    c = e.mean(axis=0)
    return float((e @ (c / (np.linalg.norm(c) or 1.0))).mean())


def _split_loose(embeddings: np.ndarray, labels: np.ndarray, min_size: int, depth: int = 3) -> np.ndarray:
    """Re-cluster each loose group on its own. Seen against the whole library, siblings' childhood faces
    form one dense blob; alone, the blob separates into one group per kid."""
    from sklearn.cluster import HDBSCAN

    labels = labels.copy()
    next_label = labels.max() + 1
    for _ in range(depth):
        split_any = False
        for g in set(labels.tolist()) - {-1}:
            members = np.where(labels == g)[0]
            if len(members) < 4 * min_size or _cohesion(embeddings[members]) >= SPLIT_BELOW:
                continue
            sub = HDBSCAN(min_cluster_size=max(min_size, len(members) // 50), min_samples=5,
                          algorithm="brute" if len(members) <= 12_000 else "ball_tree",
                          copy=True).fit_predict(embeddings[members].astype(np.float32))
            if len(set(sub.tolist()) - {-1}) < 2:
                continue
            for k in set(sub.tolist()):
                labels[members[sub == k]] = -1 if k == -1 else next_label
                next_label += k != -1
            split_any = True
        if not split_any:
            break
    return labels


COHESION = 0.5  # a group member's similarity to the group's average face; same-person faces sit around 0.8


def _drop_outliers(embeddings: np.ndarray, labels: np.ndarray, min_size: int) -> np.ndarray:
    """Take faces that only loosely resemble their group back out of it (HDBSCAN will attach a borderline
    face to the nearest dense group), and dissolve groups left too small."""
    labels = labels.copy()
    for g in set(labels.tolist()) - {-1}:
        members = np.where(labels == g)[0]
        e = embeddings[members]
        # Compare each face with the average of the *other* members, so a stray face can't vouch for itself.
        others = e.sum(axis=0) - e
        sim = np.einsum("ij,ij->i", e, others) / np.maximum(np.linalg.norm(others, axis=1), 1e-9)
        labels[members[sim < COHESION]] = -1
        if (labels == g).sum() < min_size:
            labels[labels == g] = -1
    return labels


def quality(det_score: float, size_px: int, sharpness: float, landmarks: np.ndarray) -> float:
    """0-1 score for picking representative faces: confident, big, sharp and facing the camera."""
    left_eye, right_eye, nose = landmarks[0], landmarks[1], landmarks[2]
    eye_dist = float(np.linalg.norm(right_eye - left_eye)) or 1.0
    yaw = abs(float(nose[0] - (left_eye[0] + right_eye[0]) / 2)) / eye_dist  # 0 when looking straight on
    frontal = max(0.0, 1.0 - 2.0 * yaw)
    return round(det_score * min(1.0, size_px / 120) * min(1.0, sharpness / 250) ** 0.5 * (0.3 + 0.7 * frontal), 4)
