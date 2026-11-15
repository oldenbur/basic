"""Submit photos to the Message Batches API, collect the answers, and keep spending under the daily cap.

Flow: the pilot sends the same ~300 highlights to each model (answers are kept for comparison, not applied). You
pick a model; its pilot answers are applied and the backfill sends the remaining highlights in batches of
`tag_batch_size`, at most `tag_max_open_batches` at a time, as today's cap allows. Bursts and near-duplicates
send one photo and copy its answer to the rest.
"""

import json
import logging
from collections import Counter

from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from photoindex.config import get_settings
from photoindex.models import AppSetting, Photo, PhotoAI, TagRun
from photoindex.sources import PhotoSource
from photoindex.tagging import client as tag_client
from photoindex.tagging import pricing
from photoindex.tagging.apply import apply
from photoindex.tagging.prompt import PROMPT_VERSION
from photoindex.tagging.requests import params, prepare
from photoindex.worker.stages import faces as faces_stage

log = logging.getLogger(__name__)
DEFAULTS = {"model": None, "daily_cap": 25.0, "paused": False}
MAX_ATTEMPTS = 3
MIN_SUBMIT = 25  # don't send dribbles of photos when the cap is nearly used up
NEAR_DUP_BITS = 4  # phash Hamming distance for "the same shot"
PILOT_SIZE = 300


class CapReached(Exception):
    pass


# --- Settings and spend ----------------------------------------------------------------------------------------


def get_config(session: Session) -> dict:
    row = session.get(AppSetting, "tagging")
    return DEFAULTS | (row.value if row else {})


def set_config(session: Session, **changes) -> dict:
    cfg = get_config(session) | changes
    row = session.get(AppSetting, "tagging")
    if row is None:
        session.add(AppSetting(key="tagging", value=cfg))
    else:
        row.value = cfg
    session.commit()
    return cfg


def spent_today(session: Session) -> float:
    """Dollars committed today (UTC): measured cost of finished batches, the estimate for ones still running."""
    return float(session.scalar(
        select(func.coalesce(func.sum(func.coalesce(TagRun.cost_usd, TagRun.est_cost_usd)), 0))
        .where(TagRun.created_at >= func.date_trunc("day", func.now()), TagRun.status != "failed")
    ))


def per_photo(session: Session, model: str) -> float | None:
    """Measured average cost per photo for `model`, once there are enough answers to trust it."""
    n, avg = session.execute(
        select(func.count(), func.avg(PhotoAI.cost_usd)).join(TagRun, TagRun.id == PhotoAI.run_id)
        .where(TagRun.model == model, PhotoAI.cost_usd.is_not(None))
    ).one()
    return float(avg) if n >= 20 else None


def estimate(session: Session, model: str, photos: int) -> float:
    return pricing.estimate(model, photos, per_photo(session, model))


# --- What to send ------------------------------------------------------------------------------------------------


def _in_scope():
    return text(faces_stage.SCOPE.replace("in_processing_set", "photos.in_processing_set")
                .replace("NOT ignored", "NOT photos.ignored"))


def plan_followers(session: Session) -> int:
    """Among highlights not tagged yet, mark burst shots and near-duplicates (same event, phash within
    NEAR_DUP_BITS) as followers of one representative, so only it is sent. Returns photos marked."""
    rows = session.execute(
        select(Photo.id, Photo.burst_group_id, Photo.phash, Photo.folder_id, Photo.face_count)
        .where(_in_scope(), ~Photo.deleted, Photo.tag_status == "pending", Photo.ai_id.is_(None))
        .order_by(Photo.id)
    ).all()
    parent = {r.id: r.id for r in rows}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a, b):
        parent[find(b)] = find(a)

    by_burst, by_folder = {}, {}
    for r in rows:
        if r.burst_group_id is not None:
            if r.burst_group_id in by_burst:
                union(by_burst[r.burst_group_id], r.id)
            else:
                by_burst[r.burst_group_id] = r.id
        if r.phash:
            by_folder.setdefault(r.folder_id, []).append(r)
    for group in by_folder.values():
        hashes = [(r.id, int(r.phash, 16)) for r in group]
        for i, (a, ha) in enumerate(hashes):
            for b, hb in hashes[i + 1:]:
                if (ha ^ hb).bit_count() <= NEAR_DUP_BITS:
                    union(a, b)

    groups: dict[int, list] = {}
    for r in rows:
        groups.setdefault(find(r.id), []).append(r)
    marked = []
    for members in groups.values():
        if len(members) < 2:
            continue
        rep = max(members, key=lambda r: (r.face_count or 0, -r.id))  # the shot with the most faces seen
        marked += [dict(id=r.id, tag_status="follower", tag_source_id=rep.id) for r in members if r.id != rep.id]
    if marked:
        session.execute(update(Photo), marked)
        session.commit()
    return len(marked)


def pending_ids(session: Session, limit: int) -> list[int]:
    return list(session.scalars(
        select(Photo.id).where(_in_scope(), ~Photo.deleted, Photo.tag_status == "pending").order_by(Photo.id)
        .limit(limit)
    ))


def pilot_sample(session: Session, size: int = PILOT_SIZE) -> list[int]:
    """Highlights spread evenly over the years (and cameras within a year), in a fixed pseudo-random order."""
    return list(session.execute(text(f"""
        SELECT id FROM (
          SELECT photos.id, row_number() OVER (
                   PARTITION BY coalesce(extract(year FROM taken_at)::int, f.year)
                   ORDER BY md5(coalesce(camera_model, '') || photos.id::text)) AS rn
          FROM photos LEFT JOIN folders f ON f.id = photos.folder_id
          WHERE {_in_scope().text} AND NOT photos.deleted AND photos.tag_status <> 'follower'
        ) s ORDER BY rn, md5(id::text) LIMIT :n
    """), {"n": size}).scalars())


# --- Submit -----------------------------------------------------------------------------------------------------


def submit(session: Session, source: PhotoSource, model: str, ids: list[int], kind: str,
           check_cap: bool = True) -> TagRun | None:
    """Send `ids` to `model` as one batch. Backfill photos move to 'queued'; pilot photos are left as they are."""
    if model not in pricing.MODELS:
        raise ValueError(f"unknown model {model!r}")
    if not ids:
        return None
    est = estimate(session, model, len(ids))
    if check_cap:
        cap, spent = get_config(session)["daily_cap"], spent_today(session)
        if spent + est > cap:
            raise CapReached(f"would spend ${spent + est:.2f} today; the cap is ${cap:.2f}")
    items = prepare(session, source, ids, get_settings().workers)
    if not items:
        return None
    reqs = [{"custom_id": f"p{it.photo_id}", "params": params(model, it)} for it in items]
    batch = tag_client.get_client().messages.batches.create(requests=reqs)
    run = TagRun(kind=kind, model=model, prompt_version=PROMPT_VERSION, batch_id=batch.id, status="submitted",
                 requests=len(items), est_cost_usd=pricing.estimate(model, len(items), per_photo(session, model)))
    session.add(run)
    session.flush()
    session.add_all(PhotoAI(photo_id=it.photo_id, run_id=run.id, status="queued", base_rotation=it.rotation)
                    for it in items)
    if kind == "backfill":
        session.execute(update(Photo).where(Photo.id.in_([it.photo_id for it in items])).values(tag_status="queued"))
    session.commit()
    log.info("tag: submitted %s batch %s: %d photos to %s (~$%.2f)", kind, batch.id, len(items), model, est)
    return run


def start_pilot(session: Session, source: PhotoSource, size: int = PILOT_SIZE,
                models: list[str] | None = None) -> list[TagRun]:
    models = models or list(pricing.MODELS)
    if session.scalar(select(func.count()).where(TagRun.kind == "pilot", TagRun.status != "failed")):
        raise ValueError("a pilot has already run; see the Compare page")
    plan_followers(session)
    ids = pilot_sample(session, size)
    total = sum(estimate(session, m, len(ids)) for m in models)
    cap, spent = get_config(session)["daily_cap"], spent_today(session)
    if spent + total > cap:
        raise CapReached(f"the pilot would cost about ${total:.2f}; today's cap leaves ${cap - spent:.2f}")
    return [run for m in models if (run := submit(session, source, m, ids, "pilot", check_cap=False))]


# --- Collect ----------------------------------------------------------------------------------------------------


def _error_text(result) -> tuple[str, bool]:
    """(message, retryable) for a request that didn't succeed."""
    if result.type in ("expired", "canceled"):
        return result.type, True
    err = getattr(result, "error", None)
    inner = getattr(err, "error", err)
    etype, msg = getattr(inner, "type", "error"), getattr(inner, "message", "")
    return f"{etype}: {msg}"[:500], etype not in ("invalid_request", "invalid_request_error")


def _collect(session: Session, run: TagRun) -> Counter:
    stats: Counter = Counter()
    rows = {a.photo_id: a for a in session.scalars(select(PhotoAI).where(PhotoAI.run_id == run.id))}
    retry, failed = [], []
    for res in tag_client.get_client().messages.batches.results(run.batch_id):
        pid = int(res.custom_id.lstrip("p"))
        ai = rows.get(pid)
        if ai is None or ai.status != "queued":
            continue
        r = res.result
        if r.type == "succeeded":
            msg = r.message
            u = msg.usage
            ai.input_tokens, ai.output_tokens = u.input_tokens, u.output_tokens
            ai.cache_read_tokens = u.cache_read_input_tokens or 0
            ai.cache_write_tokens = u.cache_creation_input_tokens or 0
            ai.cost_usd = pricing.cost(run.model, ai.input_tokens, ai.output_tokens, ai.cache_read_tokens,
                                       ai.cache_write_tokens)
            text_out = "".join(b.text for b in msg.content if b.type == "text")
            if msg.stop_reason == "refusal":
                ai.status, ai.error = "refused", "the model declined to describe this photo"
            else:
                try:
                    ai.result, ai.status = json.loads(text_out), "done"
                except ValueError:
                    ai.status, ai.error = "error", f"unreadable answer (stop: {msg.stop_reason})"
        else:
            ai.status = "error"
            ai.error, retryable = _error_text(r)
            if not retryable:
                failed.append(pid)
        if ai.status == "refused":
            failed.append(pid)
        elif ai.status == "error" and pid not in failed:
            retry.append(pid)
        stats[ai.status] += 1
    session.commit()

    if run.kind == "backfill":
        for pid, ai in rows.items():
            if ai.status == "done":
                photo = session.get(Photo, pid)
                apply(session, photo, ai)
        for pid in retry + failed:
            photo = session.get(Photo, pid)
            photo.tag_attempts += 1
            give_up = pid in failed or photo.tag_attempts >= MAX_ATTEMPTS
            photo.tag_status = "error" if give_up else "pending"
            photo.error = f"tag: {rows[pid].error}"[:500]
        # Requests missing from the results (shouldn't happen) go back to the queue.
        lost = [pid for pid, ai in rows.items() if ai.status == "queued"]
        if lost:
            session.execute(update(Photo).where(Photo.id.in_(lost), Photo.tag_status == "queued")
                            .values(tag_status="pending"))
            session.execute(update(PhotoAI).where(PhotoAI.run_id == run.id, PhotoAI.status == "queued")
                            .values(status="error", error="missing from batch results"))
    run.succeeded, run.errored = stats["done"], sum(v for k, v in stats.items() if k != "done")
    run.cost_usd = float(session.scalar(select(func.coalesce(func.sum(PhotoAI.cost_usd), 0))
                                        .where(PhotoAI.run_id == run.id)))
    run.status, run.ended_at = "ended", func.now()
    session.commit()
    return stats


def poll(session: Session) -> Counter:
    """Check open batches; collect the ones that finished."""
    stats: Counter = Counter()
    for run in session.scalars(select(TagRun).where(TagRun.status.in_(("submitted", "collecting")))
                               .order_by(TagRun.id)).all():
        if run.status == "submitted":
            batch = tag_client.get_client().messages.batches.retrieve(run.batch_id)
            if batch.processing_status != "ended":
                stats["running"] += 1
                continue
            # Claim it, so a second poller (CLI and the API's worker) doesn't collect it too.
            claimed = session.execute(update(TagRun).where(TagRun.id == run.id, TagRun.status == "submitted")
                                      .values(status="collecting")).rowcount
            session.commit()
            if not claimed:
                continue
        stats.update(_collect(session, run))
        stats["batches_ended"] += 1
        log.info("tag: batch %s (%s, %s) ended: %s", run.batch_id, run.kind, run.model, dict(stats))
    return stats


# --- Choose and run the backfill ---------------------------------------------------------------------------------


def choose(session: Session, model: str) -> int:
    """Tag everything with `model` from now on. Its pilot answers are applied right away. Returns photos applied."""
    if model not in pricing.MODELS:
        raise ValueError(f"unknown model {model!r}")
    set_config(session, model=model, paused=False)
    applied = 0
    for ai in session.scalars(
        select(PhotoAI).join(TagRun, TagRun.id == PhotoAI.run_id).join(Photo, Photo.id == PhotoAI.photo_id)
        .where(TagRun.kind == "pilot", TagRun.model == model, TagRun.prompt_version == PROMPT_VERSION,
               PhotoAI.status == "done", Photo.tag_status.in_(("pending", "error")))
    ).all():
        apply(session, session.get(Photo, ai.photo_id), ai)
        applied += 1
    return applied


def tick(session: Session, source: PhotoSource) -> dict:
    """One round of the background worker: collect finished batches, then send more if there's room."""
    if not get_settings().anthropic_api_key:
        return {"skipped": "no ANTHROPIC_API_KEY"}
    out: dict = {"poll": dict(poll(session))}
    if out["poll"].get("batches_ended"):
        _redetect_rotated(session, source)
    cfg = get_config(session)
    if not cfg["model"] or cfg["paused"]:
        return out
    s = get_settings()
    open_runs = session.scalar(select(func.count()).where(TagRun.kind == "backfill",
                                                          TagRun.status.in_(("submitted", "collecting"))))
    if open_runs >= s.tag_max_open_batches:
        return out
    out["followers"] = plan_followers(session)
    ids = pending_ids(session, s.tag_batch_size)
    if not ids:
        return out
    room = cfg["daily_cap"] - spent_today(session)
    each = estimate(session, cfg["model"], 1)
    n = min(len(ids), int(room / each)) if each > 0 else len(ids)
    if n < min(MIN_SUBMIT, len(ids)):
        out["waiting"] = "daily cap"
        return out
    run = submit(session, source, cfg["model"], ids[:n], "backfill")
    out["submitted"] = run.requests if run else 0
    return out


def _redetect_rotated(session: Session, source: PhotoSource) -> None:
    """Photos the answers turned upright need their faces found again."""
    if session.scalar(select(func.count()).where(_in_scope(), Photo.face_status == "pending")):
        faces_stage.run(session, source, get_settings().workers)


def status(session: Session) -> dict:
    cfg = get_config(session)
    counts = dict(session.execute(
        select(Photo.tag_status, func.count()).where(_in_scope(), ~Photo.deleted).group_by(Photo.tag_status)
    ).all())
    todo = counts.get("pending", 0) + counts.get("queued", 0)
    runs = session.scalars(select(TagRun).order_by(TagRun.id.desc()).limit(30)).all()
    models = []
    for m in pricing.MODELS.values():
        pp = per_photo(session, m.id)
        models.append(dict(id=m.id, label=m.label, per_photo=pp, measured=pp is not None,
                           estimate_all=pricing.estimate(m.id, sum(counts.values()), pp),
                           estimate_remaining=pricing.estimate(m.id, todo, pp)))
    spent = spent_today(session)
    open_runs = sum(1 for r in runs if r.status in ("submitted", "collecting"))
    if not cfg["model"]:
        state = "pilot" if any(r.kind == "pilot" for r in runs) else "not_started"
    elif cfg["paused"]:
        state = "paused"
    elif todo == 0 and not open_runs:
        state = "done"
    elif counts.get("pending", 0) and not open_runs and spent >= cfg["daily_cap"] - estimate(session, cfg["model"], MIN_SUBMIT):
        state = "waiting_cap"
    else:
        state = "running"
    tagged = session.scalar(select(func.count()).where(_in_scope(), ~Photo.deleted, Photo.ai_id.is_not(None)))
    return dict(
        config=cfg, state=state, spent_today=round(spent, 4), counts=counts, models=models, tagged=tagged,
        has_key=bool(get_settings().anthropic_api_key),
        total_cost=float(session.scalar(select(func.coalesce(func.sum(func.coalesce(TagRun.cost_usd, TagRun.est_cost_usd)), 0))
                                        .where(TagRun.status != "failed"))),
        runs=[dict(id=r.id, kind=r.kind, model=r.model, batch_id=r.batch_id, status=r.status, requests=r.requests,
                   succeeded=r.succeeded, errored=r.errored, est_cost_usd=r.est_cost_usd, cost_usd=r.cost_usd,
                   created_at=r.created_at.isoformat() if r.created_at else None,
                   ended_at=r.ended_at.isoformat() if r.ended_at else None) for r in runs],
    )
