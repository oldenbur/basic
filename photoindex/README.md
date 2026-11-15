# PhotoIndex

Index a Dropbox photo library laid out as `YYYY.album/yyMMDD.ST.event/` (or `yyMMDD.place/` for trips outside
the US), validate folder names, link `yy.highlights/` copies to their originals, and browse it all in a web UI.
Folders that don't follow the scheme are ignored: listed on the Issues page, but never linked, processed or shown. Later phases add search, slideshows, face clustering
and AI tagging. The plan is in `~/.claude/plans/i-have-been-collecting-luminous-music.md`.

## Pipeline (Phase 1)

| Stage | What it does | Runs on |
|---|---|---|
| `sync` | Mirrors folders and image metadata from Dropbox. Incremental via a saved cursor; handles deletes and moves. | everything |
| `parse` | Classifies folders (year / event / highlights / ignored), flags naming issues, suggests renames. | every folder |
| `link` | Matches highlight copies to originals: content hash → filename stem → stem + EXIF time. Computes the processing set. | highlights |
| `meta` | Reads EXIF from the first 128KB of each file: date, GPS, camera. Flags dates that disagree with the event folder; groups bursts. | processing set |
| `thumbs` | Dropbox-rendered 640px JPEGs → S3/R2, plus a perceptual hash. | processing set |
| `faces` | Finds faces in the 2048px copy (InsightFace buffalo_l via onnxruntime, on the CPU), stores a 512-d embedding and a 160px crop per face, then matches and regroups (below). | highlights |

The **processing set** is every original that has a highlight copy, plus any highlight with no findable
original, plus any folder you tick "Process all photos here" on in the UI. Nothing in Dropbox is ever modified.

## Search, themes and slideshows (Phase 2)

- **Search** (`/search`) covers the processing set: highlights plus any folders ticked "Process all photos here".
  Event-name text is split on CamelCase (`MooseRiverBWCA` → moose river bwca), matched by word prefix, and
  tolerant of typos in longer words; `|` separates alternatives. Filters: years, months/seasons, state or
  "abroad", camera, GPS, highlights only. Each image appears once: byte-identical copies filed in two events
  collapse, and by default so do bursts.
- **Themes** (`/themes`) are saved searches. `photoindex seed-themes` adds a starter set drafted from the event
  names (Skiing, Fourteeners, Camping & backcountry, …); edit or delete them freely.
- **Slideshow** (`/play?theme=<id>`): keyboard (space, ←/→, F, C, Esc) and swipe, next 5 images preloaded,
  captions, screen kept awake. Default order shuffles events and plays each in date order.
- **Large images** (2048px) are rendered by Dropbox the first time a photo is shown (~1s) and kept in S3/R2
  after that. When a highlight was re-exported (edited), the edited copy is what's shown. "Prepare" on a theme
  makes them all ahead of time.

## People (Phase 3)

Everything runs locally; no photo or face data leaves the machine except crops going to your own S3/R2 bucket.

- **Detection:** SCRFD + ArcFace from InsightFace's `buffalo_l` (downloaded on first use to
  `~/.cache/photoindex/models`, checksums pinned; licensed for non-commercial use). Faces under 40px are skipped.
- **Groups:** unnamed faces are clustered with HDBSCAN on the full 512-d embeddings. Loose groups (average
  similarity to their centre under 0.68) are re-clustered on their own, which separates siblings whose childhood
  faces blur together library-wide; then faces that only loosely resemble their group are taken back out. Tuned
  for pure groups over complete ones: a person often shows up as several groups, and the same name merges them.
- **Matching:** a face is labelled automatically only when its 3 nearest faces *you* confirmed for a person
  average ≥ 0.55 cosine similarity; 0.45–0.55 goes to the review queue. Only your own labels are used as
  references, so a wrong automatic match can't spread, and "not this person" is remembered per face.
- **UI:** People (name groups, leave out wrong faces), a person page (photos by year, fix faces, merge, play
  "through the years"), a Y/N review queue, and face boxes in the lightbox (`F`). Search and themes gain
  "with" (any / all together) and group-size filters.
- `photoindex stage faces` finds faces; `photoindex stage people` re-matches and regroups without detecting.

## Run it on a laptop

```sh
docker compose -f deploy/docker-compose.dev.yml up -d   # Postgres+pgvector, SeaweedFS (S3)
cd backend
cp .env.example .env                                    # add Dropbox app key/secret
uv sync
uv run photoindex dropbox-auth                          # open the printed URL and click Allow, then:
uv run photoindex dropbox-auth <code>                   # saves DROPBOX_REFRESH_TOKEN into .env
uv run photoindex dropbox-check                         # lists the folders under PHOTO_ROOT
uv run photoindex migrate
uv run photoindex run                                   # or: stage sync|parse|link|meta|thumbs
uv run photoindex seed-themes                           # optional starter themes
uv run photoindex serve                                 # API on :8000
```

UI (no local Node needed):

```sh
cd frontend
docker run --rm -p 5173:5173 -e API_TARGET=http://host.docker.internal:8000 -e CHOKIDAR_USEPOLLING=true \
  -v "$PWD":/app -w /app node:22-alpine sh -c "npm install && npm run dev -- --host 0.0.0.0"
```

Then open http://localhost:5173.

To try it without Dropbox, set `SOURCE=local` and `PHOTO_ROOT=/some/folder` in `.env`; any directory laid out
like the library works. To use Cloudflare R2 instead of SeaweedFS, see `.env.example`.

## Tests

```sh
cd backend && uv run pytest
```

The end-to-end tests build a small fake library (exact and re-exported highlight copies, a filename-counter
collision, bursts, misnamed folders) and run the whole pipeline and API against the dev Postgres and S3. They
are skipped if Postgres isn't running.
