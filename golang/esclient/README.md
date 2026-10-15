# Elasticsearch sandbox

A single-node Elasticsearch container plus a Go client for experimenting with document storage and search.

- Elasticsearch 9.5.2 at `http://localhost:9200`
- Security is disabled: plain HTTP, no auth
- Storage is ephemeral (tmpfs): all data is lost when the container stops

## Usage

```sh
./es.sh up       # start the container and wait until healthy
./es.sh ping     # run the Go client to check connectivity
./es.sh status   # cluster health via curl
./es.sh logs     # follow container logs
./es.sh down     # stop and discard everything
```

To use a different server, set `ES_URL` or pass `-url` to the client: `./es.sh ping -url http://host:9200`.
