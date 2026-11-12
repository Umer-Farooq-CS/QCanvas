#!/bin/bash
# usage: sample_stats.sh <out.csv> <stopfile> [interval]
out=$1; stop=$2; iv=${3:-30}
echo "ts,name,cpu,mem" > "$out"
while [ ! -f "$stop" ]; do
  ts=$(date +%H:%M:%S)
  docker stats --no-stream --format '{{.Name}},{{.CPUPerc}},{{.MemUsage}}' qcanvas_backend qcanvas_postgres qcanvas_redis | sed "s/^/$ts,/" >> "$out"
  sleep "$iv"
done
