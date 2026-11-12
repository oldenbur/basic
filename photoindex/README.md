# PhotoIndex

Index a Dropbox photo library laid out as `YYYY/yyMMDD.ST.event/`, validate folder names, link `highlights/`
copies to their originals, and browse it all in a web UI. Later phases add search, slideshows, face clustering
and AI tagging. The plan is in `~/.claude/plans/i-have-been-collecting-luminous-music.md`.

## Pipeline (Phase 1)

| Stage | What it does | Runs on |
|---|---|---|
| `sync` | Mirrors folders and image metadata from Dropbox. Incremental via a saved cursor; handles deletes and moves. | everything |
| `parse` | Classifies folders (year / event / highlights / ...), flags naming issues, suggests renames. | every folder |
| `link` | Matches highlight copies to originals: content hash → filename stem → stem + EXIF time. Computes the processing set. | highlights |
| `meta` | Reads EXIF from the first 128KB of each file: date, GPS, camera. Flags dates that disagree with the event folder; groups bursts. | processing set |
| `thumbs` | Dropbox-rendered 640px JPEGs → S3/R2, plus a perceptual hash. | processing set |

The **processing set** is every original that has a highlight copy, plus any highlight with no findable
original, plus any folder you tick "Process all photos here" on in the UI. Nothing in Dropbox is ever modified.

## Run it on a laptop

```sh
docker compose -f deploy/docker-compose.dev.yml up -d   # Postgres+pgvector, SeaweedFS (S3)
cd backend
cp .env.example .env                                    # add Dropbox app key/secret
uv sync
uv run photoindex dropbox-auth                          # paste the printed DROPBOX_REFRESH_TOKEN into .env
uv run photoindex migrate
uv run photoindex run                                   # or: stage sync|parse|link|meta|thumbs
uv run photoindex serve                                 # API on :8000
```

UI (no local Node needed):

```sh
cd frontend
docker run --rm -p 5173:5173 -e API_TARGET=http://host.docker.internal:8000 \
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
