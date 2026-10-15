#!/usr/bin/env bash
# Helper for the Elasticsearch sandbox: manage the container and run the Go client.
set -euo pipefail

cd "$(dirname "$0")"

ES_URL="${ES_URL:-http://localhost:9200}"

usage() {
  cat <<USAGE
usage: $0 <command> [args]

commands:
  up       start Elasticsearch and wait until healthy
  down     stop Elasticsearch and discard all data
  logs     follow Elasticsearch logs
  status   print cluster health
  ping     run the Go ping client (extra args passed through)
USAGE
  exit 1
}

cmd="${1:-}"
[[ $# -gt 0 ]] && shift

case "$cmd" in
  up)     docker compose up -d --wait ;;
  down)   docker compose down -v ;;
  logs)   docker compose logs -f elasticsearch ;;
  status) curl -fsS "$ES_URL/_cluster/health?pretty" ;;
  ping)   go run ./cmd/ping "$@" ;;
  *)      usage ;;
esac
