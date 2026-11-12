import argparse
import json
import logging


def main() -> None:
    ap = argparse.ArgumentParser(prog="photoindex")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate", help="apply database migrations")
    sub.add_parser("dropbox-auth", help="one-time OAuth flow; prints DROPBOX_REFRESH_TOKEN")
    st = sub.add_parser("stage", help="run one pipeline stage")
    st.add_argument("name", choices=("sync", "parse", "link", "meta", "thumbs"))
    run = sub.add_parser("run", help="run the whole pipeline")
    run.add_argument("--loop", type=int, metavar="SECONDS", help="repeat forever with this pause between runs")
    sub.add_parser("stats", help="print pipeline counts")
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
            from photoindex.sources.dropbox_source import run_auth_flow

            s = get_settings()
            print("\nDROPBOX_REFRESH_TOKEN=" + run_auth_flow(s.dropbox_app_key, s.dropbox_app_secret))
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
        case "serve":
            import uvicorn

            uvicorn.run("photoindex.api.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
