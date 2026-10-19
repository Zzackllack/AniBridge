# Finite collector comparison

Runs on an authorized Linux host with the old and new local worker images.
No competing collector is started. Do not mount real worker state into these
commands. `run.py baseline` requests three fixed season pages and at most six
detail pages per season (21 requests), with two-second spacing. Candidate uses
three season requests and compares normalized rows against the same saved
inputs. Profiles use 16 requests total, two small samples per header/pool case.
Each live command has a 240-second deadline. No media is fetched.

Raw season/detail bodies and normalized inputs remain private disposable scratch;
only numeric results belong in the evidence directory. Live headers do not prove
browser TLS/JavaScript parity. A response sample cannot justify an arbitrary
sustained rate. The default retains 2-second spacing and two/provider fetch slots.

```sh
# Named, owned scratch on the authorized Linux host, writable by this UID.
mkdir -p "$COLLECTOR_BENCHMARK_DIR/samples"
# Mount this script directory at /scripts and scratch at /benchmark.
docker run --rm --user "$(id -u)" --memory=512m --memory-swap=512m \
  --cpus=2 --pids-limit=64 -v "$PWD/scripts/catalog/collector_benchmark:/scripts:ro" \
  -v "$COLLECTOR_BENCHMARK_DIR:/benchmark" --entrypoint python \
  "$BASELINE_WORKER_IMAGE" /scripts/run.py baseline /benchmark/samples \
  > "$COLLECTOR_BENCHMARK_DIR/baseline.json"
docker run --rm --user "$(id -u)" --memory=512m --memory-swap=512m \
  --cpus=2 --pids-limit=64 -v "$PWD/scripts/catalog/collector_benchmark:/scripts:ro" \
  -v "$COLLECTOR_BENCHMARK_DIR:/benchmark" --entrypoint python \
  "$CANDIDATE_WORKER_IMAGE" /scripts/run.py candidate /benchmark/samples \
  > "$COLLECTOR_BENCHMARK_DIR/candidate.json"
```

Use `profiles` with the candidate for the header/pool comparison. Use `replay.py
/benchmark/samples baseline` and `... candidate` in matching images with
`--network none`. Replay seeds parent coordinates to isolate season work; real
parser children, durable checkpoints, publication/query totals and reopened
first-seen identities are verified. It does not establish full title discovery
or full bootstrap. Baseline fetches the bounded six detail inputs per season;
candidate admits all trustworthy rows supplied by those season pages. Report
that difference alongside time and request counts, rather than claiming equal
whole-catalog work.

The October 8 outputs are in spec020's `evidence/collector-repair-2026-10-08`.
Mapping comparison used independent SQLite backup copies from read-only retained
volumes, 50 unresolved title caches/provider and those same three season inputs.
Production ledgers were never written by that experiment. Delete only the owned
scratch after retaining sanitized numeric results; keep pilot volumes/backups.
