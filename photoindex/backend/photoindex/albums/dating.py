"""Date the album events with Claude (Message Batches API).

One request per event: every print in it, in album order, with who is recognised in each. Every request shares a
cached prefix: the instructions, the family timeline, and the confirmed reference prints (houses, family homes,
the school, trips, occasions). The model answers with a month and a range for each print, the apparent ages of
the children it can see, which reference a print matches, and prints that look like a different occasion.

These are raw estimates. Smoothing them along album order and anchoring them on the timeline comes next
(interpolation); nothing here moves or copies a file.
"""

import base64
import io
import json
import logging
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from PIL import Image
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from photoindex import storage
from photoindex.albums.names import order_key, page_of
from photoindex.faces.cluster import AUTO_ASSIGN
from photoindex.models import (AlbumDateAnswer, AlbumDateRun, AlbumEvent, AlbumFace, AlbumRef, AlbumRefExample,
                               Person, Photo)
from photoindex.tagging import client as tag_client
from photoindex.tagging import pricing

log = logging.getLogger(__name__)
PROMPT_VERSION = 1
MODEL = "claude-opus-5-5"
EFFORT = "medium"
MAX_TOKENS = 16000
PRINT_PX = 512  # long side of each event print sent
REF_PX = 448  # long side of each reference example
REFS_PER_LABEL = 4
MIN_FACE_QUALITY = 0.05
PILOT_EVENTS = 20

# From the family timeline (Google Sheet "oldenburg_timeline").
TIMELINE = """\
1972-12  Mark & Ann's wedding (Galena, IL)
1975-06  Mark's MBA (Notre Dame, South Bend, IN)
1976-10  Paul born (Galena, IL)
1978-04  Rico born (Galena, IL)
1979-04  Move to Rochester, MN
1980-07  Angela born (Rochester, MN)
1983-11  Joe passing
1983-12  Move to Danbury, CT (Paul in grade 1)
1984-05  Joe born (Danbury, CT)
1985-12  Move back to Rochester, MN (Paul in grade 3)
1987-01  Martha born (Rochester, MN)
1988-07  Itasca trip
1990-07  Colorado / Grand Canyon trip
1991-07  Niagara Falls trip
1993-07  Glacier / BC trip"""

# The children, as named on the People pages, and their birth months: their apparent ages date a print best.
CHILDREN = [
    ("Paul Oldenburg", "Paul", date(1976, 10, 1)),
    ("Eric Oldenburg", "Rico", date(1978, 4, 1)),
    ("Angela Oldenburg", "Angela", date(1980, 7, 1)),
    ("Joseph Oldenburg", "Joe", date(1984, 5, 1)),
    ("Martha Oldenburg", "Martha", date(1987, 1, 1)),
]

SYSTEM = """\
You date family snapshots: colour and black-and-white prints from the Oldenburg family's photo albums, scanned at \
200 dpi. No print carries a date, so the date has to come from what the prints show.

The albums are roughly in date order, page by page, but not strictly: prints were sometimes mounted out of \
order, and some pages hold older family photos or school portraits. Each request is one run of consecutive \
prints that looks like a single occasion or roll of film. It may still mix two occasions.

Clues, strongest first:
- The children's apparent ages. Their birth months are below; age plus birth month is usually the best date. \
Estimate each child's age to the half year from size, proportions, teeth and face.
- A recognised house, family home, school or trip from the reference images: it bounds the date by when the \
family lived there or travelled.
- Season and occasion: snow, leaves, Christmas trees, Easter, birthday cakes (count candles), first communions, \
graduations, swimsuits.
- Clothing, hairstyles, cars, furniture, technology; print format and colour cast.

Be honest about uncertainty: a wide range is better than a confident wrong date. A month only counts as \
"high" confidence when ages or a dated reference pin it.

Answer in the JSON format given. Months are "YYYY-MM". Number prints from 1 in the order given. In \
"reference", use a reference label exactly as written below when a print clearly shows that place or event, \
otherwise an empty string. In "ages", list only the children named below whom you can see and recognise (names \
given with a print were matched by face recognition; trust them unless the print clearly disagrees). Set \
"different_occasion" when a print clearly belongs to a different occasion from the rest of the run.

Family timeline:
{timeline}

Children (birth month):
{children}"""

MONTH = r"^\d{4}-(0[1-9]|1[0-2])$"
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["event", "prints"],
    "properties": {
        "event": {
            "type": "object", "additionalProperties": False,
            "required": ["summary", "best", "earliest", "latest", "confidence", "clues"],
            "properties": {
                "summary": {"type": "string", "description": "what the occasion is, in a few words"},
                "best": {"type": "string"}, "earliest": {"type": "string"}, "latest": {"type": "string"},
                "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                "clues": {"type": "string", "description": "the clues that set the date, one or two sentences"},
            },
        },
        "prints": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["print", "best", "earliest", "latest", "confidence", "reference", "ages",
                             "different_occasion", "caption"],
                "properties": {
                    "print": {"type": "integer"},
                    "best": {"type": "string"}, "earliest": {"type": "string"}, "latest": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                    "reference": {"type": "string"},
                    "ages": {"type": "array", "items": {
                        "type": "object", "additionalProperties": False, "required": ["name", "age"],
                        "properties": {"name": {"type": "string"}, "age": {"type": "number"}}}},
                    "different_occasion": {"type": "boolean"},
                    "caption": {"type": "string", "description": "one short line"},
                },
            },
        },
    },
}


class SpendLimit(Exception):
    pass


# --- Building requests --------------------------------------------------------------------------------------------


def _jpeg(data: bytes, px: int) -> bytes:
    with Image.open(io.BytesIO(data)) as im:
        im = im.convert("RGB")
        im.thumbnail((px, px))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=82)
        return buf.getvalue()


def _image_block(jpeg: bytes) -> dict:
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                        "data": base64.standard_b64encode(jpeg).decode()}}


def _image_tokens(jpeg: bytes) -> int:
    with Image.open(io.BytesIO(jpeg)) as im:
        return max(1, im.width * im.height // 750)


def _when(ref: AlbumRef) -> str:
    if ref.start and ref.end:
        return f"{ref.start:%Y-%m} to {ref.end:%Y-%m}"
    if ref.start:
        return f"from {ref.start:%Y-%m}"
    if ref.end:
        return f"until {ref.end:%Y-%m}"
    return "dates unknown"


def shared_prefix(session: Session, workers: int = 8) -> tuple[str, list[dict], int]:
    """(system text, reference content blocks, estimated tokens). Deterministic, so every request shares it."""
    children = "\n".join(f"{nick} ({full}): born {born:%Y-%m}" if nick != full.split()[0] else
                         f"{full}: born {born:%Y-%m}" for full, nick, born in CHILDREN)  # e.g. "Rico (Eric Oldenburg)"
    system = SYSTEM.format(timeline=TIMELINE, children=children)
    refs = session.scalars(select(AlbumRef).order_by(AlbumRef.sort, AlbumRef.id)).all()
    picks: list[tuple[AlbumRef, list[Photo]]] = []
    for ref in refs:
        photos = session.scalars(
            select(Photo).join(AlbumRefExample, AlbumRefExample.photo_id == Photo.id)
            .where(AlbumRefExample.ref_id == ref.id, AlbumRefExample.status == "confirmed")
        ).all()
        photos = sorted(photos, key=lambda p: (p.parent_path_lower, order_key(p.name)))
        if photos:  # spread the picks across the confirmed examples
            step = max(1, len(photos) // REFS_PER_LABEL)
            picks.append((ref, photos[::step][:REFS_PER_LABEL]))
    keys = [p.thumb_key for _, ps in picks for p in ps]
    with ThreadPoolExecutor(workers) as pool:
        images = dict(zip(keys, pool.map(lambda k: _jpeg(storage.get_bytes(k), REF_PX), keys), strict=True))
    blocks: list[dict] = [{"type": "text", "text": "Reference images. Each label's dates bound any print that "
                                                   "clearly shows the same place or occasion."}]
    tokens = len(system) // 4 + 40
    for ref, ps in picks:
        text = f"Reference: {ref.label} ({ref.kind}; {_when(ref)})" + (f". Look for: {ref.notes}" if ref.notes else "")
        blocks.append({"type": "text", "text": text})
        tokens += len(text) // 4 + 5
        for p in ps:
            blocks.append(_image_block(images[p.thumb_key]))
            tokens += _image_tokens(images[p.thumb_key])
    blocks[-1] = blocks[-1] | {"cache_control": {"type": "ephemeral", "ttl": "1h"}}
    return system, blocks, tokens


def _names_by_photo(session: Session, ids: list[int]) -> dict[int, list[str]]:
    """Confirmed names, plus confident automatic matches, left to right."""
    names = dict(session.execute(select(Person.id, Person.name)).all())
    out: dict[int, list[tuple[float, str]]] = defaultdict(list)
    for f in session.scalars(select(AlbumFace).where(AlbumFace.photo_id.in_(ids), ~AlbumFace.ignored)):
        who = f.person_id if f.person_id is not None else (
            f.match_person_id if (f.match_score or 0) >= AUTO_ASSIGN and f.quality >= MIN_FACE_QUALITY else None)
        if who is not None and names.get(who) not in [n for _, n in out[f.photo_id]]:
            out[f.photo_id].append((f.x, names.get(who, "?")))
    return {pid: [n for _, n in sorted(v)] for pid, v in out.items()}


def event_request(session: Session, ev: AlbumEvent, n_events: int, system: str, ref_blocks: list[dict],
                  workers: int = 8) -> tuple[dict, list[int], int]:
    """(request params, photo ids in order, estimated input tokens beyond the shared prefix)."""
    photos = sorted(session.scalars(select(Photo).where(Photo.album_event_id == ev.id)).all(),
                    key=lambda p: order_key(p.name))
    names = _names_by_photo(session, [p.id for p in photos])
    with ThreadPoolExecutor(workers) as pool:
        images = list(pool.map(lambda p: _jpeg(storage.get_bytes(p.thumb_key), PRINT_PX), photos))
    pages = sorted({pg for p in photos if (pg := page_of(p.name)) is not None})
    where = f"pages {pages[0]}-{pages[-1]}" if len(pages) > 1 else (f"page {pages[0]}" if pages else "no page")
    content: list[dict] = [{"type": "text", "text": (
        f"Album {ev.album}, run {ev.seq} of {n_events} ({where}), {len(photos)} prints in album order.")}]
    tokens = 40
    for i, (p, img) in enumerate(zip(photos, images, strict=True), 1):
        who = names.get(p.id)
        line = f"Print {i}: {p.name}" + (f". Recognised: {', '.join(who)}" if who else "")
        content += [{"type": "text", "text": line}, _image_block(img)]
        tokens += len(line) // 4 + 5 + _image_tokens(img)
    params = dict(
        model=MODEL, max_tokens=MAX_TOKENS,
        system=[{"type": "text", "text": system}],
        messages=[{"role": "user", "content": ref_blocks + content}],
        output_config={"effort": EFFORT, "format": {"type": "json_schema", "schema": SCHEMA}},
    )
    return params, [p.id for p in photos], tokens


# --- Cost --------------------------------------------------------------------------------------------------------

EST_OUTPUT_PER_PRINT = 90
EST_THINKING = 2500


def estimate(prefix_tokens: int, event_tokens: list[int], event_sizes: list[int]) -> dict:
    """Batch cost estimate. Caching in a batch is best-effort, so the range runs from 'every request reads the
    cached prefix' to 'a quarter of requests write it again'."""
    n = len(event_tokens)
    out = sum(EST_THINKING + EST_OUTPUT_PER_PRINT * s for s in event_sizes)
    own = sum(event_tokens)
    low = pricing.cost(MODEL, own, out, cache_read=prefix_tokens * n, cache_write=prefix_tokens)
    writes = max(1, n // 4)
    high = pricing.cost(MODEL, own, int(out * 1.5), cache_read=prefix_tokens * (n - writes),
                        cache_write=prefix_tokens * writes)
    return dict(events=n, prints=sum(event_sizes), prefix_tokens=prefix_tokens, low=round(low, 2), high=round(high, 2))


# --- Choosing events ---------------------------------------------------------------------------------------------


def pilot_events(session: Session, n: int = PILOT_EVENTS) -> list[AlbumEvent]:
    """Events spread evenly through each album, in proportion to its size."""
    events = session.scalars(select(AlbumEvent).order_by(AlbumEvent.album, AlbumEvent.seq)).all()
    by_album: dict[str, list[AlbumEvent]] = defaultdict(list)
    for e in events:
        by_album[e.album].append(e)
    out = []
    for album, evs in sorted(by_album.items()):
        k = max(2, round(n * len(evs) / max(len(events), 1)))
        step = len(evs) / k
        out += [evs[int(step * i + step / 2)] for i in range(k)]
    return out


def undated_events(session: Session) -> list[AlbumEvent]:
    """Events with a print that has no answer yet."""
    answered = select(func.unnest(AlbumDateAnswer.photo_ids)).where(AlbumDateAnswer.status == "done").scalar_subquery()
    ids = session.scalars(
        select(Photo.album_event_id).where(Photo.album_scan, Photo.album_event_id.is_not(None), Photo.id.not_in(answered))
        .distinct()
    ).all()
    return session.scalars(select(AlbumEvent).where(AlbumEvent.id.in_(ids)).order_by(AlbumEvent.album, AlbumEvent.seq)).all()


# --- Submit and collect -------------------------------------------------------------------------------------------


def plan(session: Session, events: list[AlbumEvent]) -> tuple[list[tuple[AlbumEvent, dict, list[int]]], dict]:
    system, ref_blocks, prefix_tokens = shared_prefix(session)
    totals = dict(session.execute(select(AlbumEvent.album, func.count()).group_by(AlbumEvent.album)).all())
    reqs, toks = [], []
    for ev in events:
        params, ids, t = event_request(session, ev, totals[ev.album], system, ref_blocks)
        reqs.append((ev, params, ids))
        toks.append(t)
    return reqs, estimate(prefix_tokens, toks, [len(ids) for _, _, ids in reqs])


def submit(session: Session, kind: str, events: list[AlbumEvent], max_usd: float,
           allow_running: bool = False) -> AlbumDateRun:
    """Send `events` as one batch, refusing if the high estimate exceeds `max_usd`."""
    if not allow_running and session.scalar(select(func.count()).select_from(AlbumDateRun).where(AlbumDateRun.status.in_(("submitted", "collecting")))):
        raise ValueError("a dating batch is still running; wait for it to finish")
    reqs, est = plan(session, events)
    if est["high"] > max_usd:
        raise SpendLimit(f"this would cost up to ${est['high']:.2f} (estimate ${est['low']:.2f}-{est['high']:.2f}); "
                         f"the limit given was ${max_usd:.2f}")
    run = AlbumDateRun(kind=kind, model=MODEL, prompt_version=PROMPT_VERSION, status="submitting",
                       requests=len(reqs), est_cost_usd=est["high"])
    session.add(run)
    session.flush()
    answers = [AlbumDateAnswer(run_id=run.id, album=ev.album, event_seq=ev.seq, photo_ids=ids) for ev, _, ids in reqs]
    session.add_all(answers)
    session.flush()
    try:
        batch = tag_client.get_client().messages.batches.create(
            requests=[{"custom_id": f"a{a.id}", "params": params} for a, (_, params, _) in zip(answers, reqs, strict=True)])
    except Exception:
        session.rollback()
        raise
    run.batch_id, run.status = batch.id, "submitted"
    session.commit()
    log.info("album dating: sent %s batch %s, %d events (~$%.2f-%.2f)", kind, batch.id, len(reqs), est["low"], est["high"])
    return run


CHUNK_EVENTS = 60  # ~2.3 MB of images per event; a batch may be at most 256 MB


def submit_rest(session: Session, max_usd: float) -> list[AlbumDateRun]:
    """Send every event that has a print without an answer, in batches of CHUNK_EVENTS. Each batch is checked
    against what's left of `max_usd` (using its high estimate) before it goes; the rest wait if it would go over."""
    events = undated_events(session)
    runs: list[AlbumDateRun] = []
    budget = max_usd
    for i in range(0, len(events), CHUNK_EVENTS):
        try:
            run = submit(session, "full", events[i:i + CHUNK_EVENTS], budget, allow_running=bool(runs))
        except SpendLimit:
            if not runs:
                raise
            log.warning("album dating: stopped after %d batches; the rest would pass $%.2f", len(runs), max_usd)
            break
        runs.append(run)
        budget -= run.est_cost_usd
    return runs


def _month(s) -> date | None:
    if isinstance(s, str) and re.match(MONTH, s.strip()):
        y, m = s.strip().split("-")
        return date(int(y), int(m), 1)
    return None


def apply_answer(session: Session, ans: AlbumDateAnswer) -> int:
    """Turn an event answer into per-print rows. Prints the model skipped get none."""
    from photoindex.models import AlbumPrintDate

    session.execute(AlbumPrintDate.__table__.delete().where(AlbumPrintDate.answer_id == ans.id))
    n = 0
    for item in (ans.result or {}).get("prints", []):
        i = item.get("print")
        if not isinstance(i, int) or not 1 <= i <= len(ans.photo_ids):
            continue
        best, lo, hi = _month(item.get("best")), _month(item.get("earliest")), _month(item.get("latest"))
        if lo and hi and lo > hi:
            lo, hi = hi, lo
        session.add(AlbumPrintDate(
            answer_id=ans.id, photo_id=ans.photo_ids[i - 1], best=best, earliest=lo, latest=hi,
            confidence=item.get("confidence"), ref_label=(item.get("reference") or "").strip() or None,
            ages=[a for a in item.get("ages") or [] if isinstance(a, dict)],
            different_occasion=bool(item.get("different_occasion")), caption=item.get("caption"),
            clues=(ans.result or {}).get("event", {}).get("clues"),
        ))
        n += 1
    return n


def _error_text(result) -> str:
    err = getattr(result, "error", None)
    inner = getattr(err, "error", err)
    return f"{result.type}: {getattr(inner, 'type', '')} {getattr(inner, 'message', '')}".strip()[:500]


def _collect(session: Session, run: AlbumDateRun) -> Counter:
    stats: Counter = Counter()
    answers = {f"a{a.id}": a for a in session.scalars(select(AlbumDateAnswer).where(AlbumDateAnswer.run_id == run.id))}
    for res in tag_client.get_client().messages.batches.results(run.batch_id):
        ans = answers.get(res.custom_id)
        if ans is not None and ans.status == "queued":
            stats.update(_store(session, run, ans, res))
    for ans in answers.values():
        if ans.status == "queued":
            ans.status, ans.error = "error", "missing from batch results"
            stats["error"] += 1
    run.succeeded, run.errored = stats["done"], stats["error"] + stats["refused"]
    run.cost_usd = float(session.scalar(select(func.coalesce(func.sum(AlbumDateAnswer.cost_usd), 0))
                                        .where(AlbumDateAnswer.run_id == run.id)))
    run.status, run.ended_at = "ended", func.now()
    session.commit()
    return stats


def _store(session: Session, run: AlbumDateRun, ans: AlbumDateAnswer, res) -> Counter:
    r = res.result
    if r.type == "succeeded":
        msg = r.message
        u = msg.usage
        ans.input_tokens, ans.output_tokens = u.input_tokens, u.output_tokens
        ans.cache_read_tokens = u.cache_read_input_tokens or 0
        ans.cache_write_tokens = u.cache_creation_input_tokens or 0
        ans.cost_usd = pricing.cost(run.model, ans.input_tokens, ans.output_tokens, ans.cache_read_tokens,
                                    ans.cache_write_tokens)
        if msg.stop_reason == "refusal":
            ans.status, ans.error = "refused", "the model declined"
        else:
            try:
                ans.result = json.loads("".join(b.text for b in msg.content if b.type == "text"))
                ans.status = "done"
                apply_answer(session, ans)
            except ValueError:
                ans.status, ans.error = "error", f"unreadable answer (stop: {msg.stop_reason})"
    else:
        ans.status, ans.error = "error", _error_text(r)
    return Counter([ans.status])


def poll(session: Session) -> Counter:
    """Collect finished dating batches (called every minute by the API's background worker)."""
    stats: Counter = Counter()
    for run in session.scalars(select(AlbumDateRun).where(AlbumDateRun.status == "submitted")).all():
        batch = tag_client.get_client().messages.batches.retrieve(run.batch_id)
        if batch.processing_status != "ended":
            stats["running"] += 1
            continue
        claimed = session.execute(update(AlbumDateRun).where(AlbumDateRun.id == run.id, AlbumDateRun.status == "submitted")
                                  .values(status="collecting")).rowcount
        session.commit()
        if claimed:
            stats.update(_collect(session, run))
            log.info("album dating: batch %s ended: %s", run.batch_id, dict(stats))
    return stats
