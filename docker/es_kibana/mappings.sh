#!/bin/bash

# see: https://www.elastic.co/guide/en/kibana/current/tutorial-load-dataset.html

curl -Ok https://download.elastic.co/demos/kibana/gettingstarted/shakespeare_6.0.json
curl -Ok https://download.elastic.co/demos/kibana/gettingstarted/accounts.zip
unzip accounts.zip
curl -Ok https://download.elastic.co/demos/kibana/gettingstarted/logs.jsonl.gz
gunzip logs.jsonl.gz

curl -X PUT "localhost:9200/shakespeare" -H 'Content-Type: application/json' -d'
{
 "mappings": {
  "doc": {
   "properties": {
    "speaker": {"type": "keyword"},
    "play_name": {"type": "keyword"},
    "line_id": {"type": "integer"},
    "speech_number": {"type": "integer"}
   }
  }
 }
}
'

GEO_MAPPING='
{
  "mappings": {
    "log": {
      "properties": {
        "geo": { "properties": { "coordinates": { "type": "geo_point" } } }
      }
    }
  }
}
'

curl -X PUT "localhost:9200/logstash-2015.05.18" -H 'Content-Type: application/json' -d"${GEO_MAPPING}"
curl -X PUT "localhost:9200/logstash-2015.05.19" -H 'Content-Type: application/json' -d"${GEO_MAPPING}"
curl -X PUT "localhost:9200/logstash-2015.05.20" -H 'Content-Type: application/json' -d"${GEO_MAPPING}"

curl -H 'Content-Type: application/x-ndjson' -XPOST 'localhost:9200/bank/account/_bulk?pretty' --data-binary @accounts.json
curl -H 'Content-Type: application/x-ndjson' -XPOST 'localhost:9200/shakespeare/doc/_bulk?pretty' --data-binary @shakespeare_6.0.json
curl -H 'Content-Type: application/x-ndjson' -XPOST 'localhost:9200/_bulk?pretty' --data-binary @logs.jsonl

curl -H 'Content-Type: application/json' -XPUT 'localhost:9200/*/_settings' -d'{"index.number_of_replicas": 0}'

