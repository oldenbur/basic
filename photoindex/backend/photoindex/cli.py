import argparse
import json
import logging


def main() -> None:
    ap = argparse.ArgumentParser(prog="photoindex")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate", help="apply database migrations")
    au = sub.add_parser("dropbox-auth", help="one-time OAuth flow: run once for a URL, then again with the code")
    au.add_argument("code", nargs="?", help="authorization code from the Dropbox approval page")
    sub.add_parser("dropbox-check", help="confirm Dropbox access and list the folders under PHOTO_ROOT")
    st = sub.add_parser("stage", help="run one pipeline stage")
    st.add_argument("name", choices=("sync", "parse", "link", "meta", "thumbs"))
    run = sub.add_parser("run", help="run the whole pipeline")
    run.add_argument("--loop", type=int, metavar="SECONDS", help="repeat forever with this pause between runs")
    sub.add_parser("stats", help="print pipeline counts")
    sub.add_parser("seed-themes", help="add the starter themes (skiing, fourteeners, ...) that don't exist yet")
    srv = sub.add_parser("serve", help="run the API server")
    srv.add_argument("--host", default="127.0.0.1")
    srv.add_argument("--port", type=int, default=8000)
    srv.add_argument("--reload", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    match args.cmd:
        case "migrate":
            from pathlib import Path

            from alembic import command
            from alembic.config import Config

            cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
            command.upgrade(cfg, "head")
        case "dropbox-auth":
            from photoindex.config import get_settings
            from photoindex.sources import dropbox_source

            s = get_settings()
            if not (s.dropbox_app_key and s.dropbox_app_secret):
                raise SystemExit("Set DROPBOX_APP_KEY and DROPBOX_APP_SECRET in .env first")
            if not args.code:
                print("Open this URL, click Allow, then run: photoindex dropbox-auth <code>")
                print(dropbox_source.auth_url(s.dropbox_app_key, s.dropbox_app_secret))
            else:
                token = dropbox_source.finish_auth(s.dropbox_app_key, s.dropbox_app_secret, args.code)
                _set_env("DROPBOX_REFRESH_TOKEN", token)
                print("Saved DROPBOX_REFRESH_TOKEN to .env. Check it with: photoindex dropbox-check")
        case "dropbox-check":
            from photoindex.sources import dropbox_source, get_source

            print(json.dumps(dropbox_source.describe(get_source()), indent=2))
        case "stage":
            from photoindex.worker.pipeline import run_stage

            print(json.dumps(run_stage(args.name), indent=2))
        case "run":
            from photoindex.worker import pipeline

            if args.loop:
                pipeline.loop(args.loop)
            else:
                print(json.dumps(pipeline.run_all(), indent=2))
        case "stats":
            from photoindex.api.queries import pipeline_stats
            from photoindex.db import session_scope

            with session_scope() as session:
                print(json.dumps(pipeline_stats(session), indent=2))
        case "seed-themes":
            from photoindex.db import session_scope
            from photoindex.themes import seed

            with session_scope() as session:
                print("added:", ", ".join(seed(session)) or "nothing (all exist)")
        case "serve":
            import uvicorn

            uvicorn.run("photoindex.api.main:app", host=args.host, port=args.port, reload=args.reload)


def _set_env(key: str, value: str, path: str = ".env") -> None:
    """Set KEY=value in .env, replacing an existing line, without echoing the value."""
    from pathlib import Path

    p = Path(path)
    lines = p.read_text().splitlines() if p.exists() else []
    lines = [ln for ln in lines if not ln.startswith(key + "=")] + [f"{key}={value}"]
    p.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
