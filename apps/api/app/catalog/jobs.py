"""Durable admission and CAS lifecycle; HTTP handlers never resolve sources."""

import json
import re
import shutil
import sqlite3
from collections.abc import Iterator
from contextlib import AbstractContextManager, closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from catalog_core import identity, magnet
from catalog_core.files import fsync_directory
from catalog_core.json_codec import dumps, require

from .output_paths import output_paths
from .quality_observations import retain as retain_quality
from .retention import DirectoryGuard, directory_guard
from .storage import writable

ACTIVE = (
    "queued",
    "resolving",
    "downloading",
    "retry_wait",
    "paused",
    "blocked",
    "cancelling",
)
QBIT = {
    "queued": "queuedDL",
    "resolving": "metaDL",
    "downloading": "downloading",
    "retry_wait": "queuedDL",
    "paused": "pausedDL",
    "blocked": "stalledDL",
    "failed": "error",
    "cancelling": "pausedDL",
    "cancelled": "pausedDL",
    "completed": "pausedUP",
}
LANGUAGES = {
    "German Dub": "de-dub",
    "Deutsch": "de-dub",
    "English Dub": "en-dub",
    "German Sub": "de-sub",
    "English Sub": "en-sub",
}


class JobError(ValueError):
    def __init__(self, code: str, status: int) -> None:
        super().__init__(code)
        self.code, self.status = code, status


def timestamp(now: int) -> str:
    return datetime.fromtimestamp(now, timezone.utc).replace(tzinfo=None).isoformat(" ")


def decode(value: str) -> tuple[str, dict, str, str | None]:
    if "ab_v=" in value:
        digest, payload, label = magnet.decode(value)
        return (
            digest,
            payload,
            label,
            identity.digest(
                "local-job-1",
                payload["provider"],
                payload["entity_id"],
                payload["language"],
                payload["mode"],
            ),
        )
    require(
        value.startswith("magnet:?") and len(value.encode()) <= 16384, "invalid magnet"
    )
    params = parse_qs(
        urlsplit(value).query,
        keep_blank_values=True,
        max_num_fields=16,
        strict_parsing=True,
    )
    require(all(len(v) == 1 for v in params.values()), "duplicate magnet fields")
    p = {key: values[0] for key, values in params.items()}
    prefixes = {key.split("_")[0] for key in p if key.startswith(("aw_", "sto_"))}
    require(len(prefixes) == 1, "mixed/missing provider prefix")
    prefix = prefixes.pop()
    provider = p.get(prefix + "_site", "aniworld.to" if prefix == "aw" else "s.to")
    require(provider in identity.PROVIDERS, "invalid provider")
    require(prefix == "aw" or provider == "s.to", "inconsistent provider")
    require(
        re.fullmatch(r"urn:btih:[0-9a-fA-F]{40}", p.get("xt", "")) is not None,
        "invalid hash",
    )
    slug = p.get(prefix + "_slug", "")
    require(
        bool(slug)
        and len(slug.encode()) <= 256
        and not any(c in slug for c in "/\\?#%")
        and slug not in (".", ".."),
        "invalid slug",
    )
    season, episode = p.get(prefix + "_s", ""), p.get(prefix + "_e", "")
    require(
        season.isdecimal()
        and episode.isdecimal()
        and len(season) <= 10
        and len(episode) <= 10
        and 0 <= int(season) <= 2**31 - 1
        and 1 <= int(episode) <= 2**31 - 1,
        "invalid coordinates",
    )
    label = p.get(prefix + "_lang", "")
    require(label in LANGUAGES, "invalid language")
    mode = p.get(prefix + "_mode", "download")
    require(mode in ("download", "strm"), "invalid mode")
    preferred = p.get(prefix + "_provider")
    require(
        preferred is None
        or 0 < len(preferred) <= 64
        and preferred.isascii()
        and all(c.isalnum() or c in "-_ " for c in preferred),
        "invalid host preference",
    )
    native_path = None
    if provider == "aniworld.to":
        suffix = (
            f"/filme/film-{int(episode)}"
            if int(season) == 0
            else f"/staffel-{int(season)}/episode-{int(episode)}"
        )
        native_path = identity.path("/anime/stream/" + slug + suffix)
    elif provider == "s.to":
        native_path = identity.path(
            f"/serie/{slug}/staffel-{int(season)}/episode-{int(episode)}"
        )
    # Legacy numbering cannot prove equivalence to v2 anchors (especially
    # specials/movies). Preserve its hash and do not fabricate that equivalence.
    payload = {
        "provider": provider,
        "slug": slug,
        "native_season": int(season),
        "native_episode": int(episode),
        "language": LANGUAGES[label],
        "mode": mode,
        "legacy": True,
        "canonical": None,
        "release_id": None,
        "entity_id": None,
        "preferred_host": preferred,
        "path": native_path,
        "kind": "episode" if native_path else None,
    }
    return p["xt"].split(":")[-1].lower(), payload, p.get("dn", slug), None


class Jobs:
    def __init__(
        self,
        filename: Path,
        download_dir: Path,
        providers: set[str],
        queue_limit: int = 1000,
        metadata_limit: int = 16 * 1024**3,
        hosts: tuple[str, ...] | None = None,
        strm_mode: str = "direct",
    ) -> None:
        self.filename, self.download_dir, self.providers = (
            filename,
            download_dir.resolve(),
            providers,
        )
        self.queue_limit, self.metadata_limit = queue_limit, metadata_limit
        self.hosts = hosts
        require(strm_mode in ("direct", "proxy"), "invalid STRM delivery mode")
        self.strm_mode = strm_mode

    def db(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.filename, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")
        return db

    def admit(
        self,
        urls: str,
        now: int,
        *,
        paused: bool = False,
        savepath: str | None = None,
        category: str | None = None,
        mapping_check=lambda payload: None,
        legacy_path=lambda payload: None,
    ) -> list[str]:
        require(len(urls.encode()) <= 128 * 1024, "form too large")
        lines = [line.strip() for line in urls.splitlines() if line.strip()]
        require(1 <= len(lines) <= 10, "invalid batch size")
        path = Path(savepath).resolve() if savepath else self.download_dir
        require(
            path.is_relative_to(self.download_dir), "save path outside download root"
        )
        decoded = [decode(line) for line in lines]
        provenance = {}
        for digest, payload, _, _ in decoded:
            if payload["provider"] not in self.providers:
                raise JobError("disabled_provider", 403)
            if payload.get("legacy") and payload["provider"] == "megakino":
                selected = legacy_path(payload)
                if selected is not None:
                    payload.update(path=identity.path(selected), kind="movie")
            provenance[digest] = mapping_check(payload)
        with closing(self.db()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            admitted = []
            for digest, payload, label, equivalence in decoded:
                existing = db.execute(
                    "SELECT c.job_id,d.payload FROM clienttask c LEFT JOIN durable_request d ON d.job_id=c.job_id WHERE c.hash=?",
                    (digest,),
                ).fetchone()
                frozen = {
                    **payload,
                    "submitted_hash": digest,
                    "original_label": label,
                    "save_path": str(path),
                    "category": category,
                    "host_preference": list(
                        dict.fromkeys(
                            (
                                [payload["preferred_host"]]
                                if payload.get("preferred_host") in self.hosts
                                else []
                            )
                            + list(self.hosts)
                        )
                    )
                    if self.hosts is not None
                    else None,
                    "canonical_provenance": (provenance[digest] or "submitted_release")
                    if payload.get("canonical")
                    else None,
                }
                if payload["mode"] == "strm":
                    frozen["strm_delivery"] = self.strm_mode
                if existing:
                    if not existing["payload"]:
                        raise JobError("identity_conflict", 409)
                    old = json.loads(existing["payload"])
                    keys = (
                        "provider",
                        "entity_id",
                        "release_id",
                        "slug",
                        "native_season",
                        "native_episode",
                        "language",
                        "mode",
                    )
                    if any(old.get(key) != payload.get(key) for key in keys):
                        raise JobError("identity_conflict", 409)
                    admitted.append(existing["job_id"])
                    continue
                # A duplicate needs no new durable state, so disk pressure must
                # not turn a successful add into a spurious failed retry.
                used = sum(
                    path.stat().st_size
                    for path in (self.filename, Path(str(self.filename) + "-wal"))
                    if path.exists()
                )
                require(
                    used < self.metadata_limit
                    and shutil.disk_usage(self.filename.parent).free >= 512 * 1024**2
                    and shutil.disk_usage(self.download_dir).free >= 512 * 1024**2,
                    "storage_full",
                )
                shared = (
                    db.execute(
                        "SELECT job_id FROM durable_request WHERE identity_key=?",
                        (equivalence,),
                    ).fetchone()
                    if equivalence
                    else None
                )
                job_id = shared["job_id"] if shared else uuid4().hex
                if not shared:
                    count = db.execute(
                        f"SELECT count(*) FROM job WHERE status IN ({','.join('?' for _ in ACTIVE)})",
                        ACTIVE,
                    ).fetchone()[0]
                    if count >= self.queue_limit:
                        raise JobError("queue_full", 503)
                    db.execute(
                        "INSERT INTO job(id,status,progress,downloaded_bytes,source_site,created_at,updated_at) VALUES(?,?,0,0,?,?,?)",
                        (
                            job_id,
                            "paused" if paused else "queued",
                            payload["provider"],
                            timestamp(now),
                            timestamp(now),
                        ),
                    )
                    db.execute(
                        "INSERT INTO durable_request(job_id,payload,identity_key) VALUES(?,?,?)",
                        (job_id, dumps(frozen).decode(), equivalence),
                    )
                db.execute(
                    "INSERT INTO clienttask(hash,name,slug,season,episode,language,site,job_id,save_path,category,added_on,state) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        digest,
                        label,
                        payload["slug"],
                        payload["native_season"] or 0,
                        payload["native_episode"] or 0,
                        payload["language"],
                        payload["provider"],
                        job_id,
                        str(path),
                        category,
                        timestamp(now),
                        "paused" if paused else "queued",
                    ),
                )
                db.execute("INSERT INTO grab_alias VALUES(?,?)", (digest, job_id))
                admitted.append(job_id)
            return admitted

    def get(self, job_id: str, *, include_hashes: bool = True) -> dict:
        with closing(self.db()) as db:
            db.execute("BEGIN")
            row = db.execute(
                "SELECT j.*,d.version,d.generation,d.attempts,d.next_retry_at,d.last_attempt_at,d.error_code,d.payload FROM job j LEFT JOIN durable_request d ON j.id=d.job_id WHERE j.id=?",
                (job_id,),
            ).fetchone()
            if row is None:
                raise JobError("not_found", 404)
            record = dict(row)
            if include_hashes:
                record["hashes"] = [
                    r[0]
                    for r in db.execute(
                        "SELECT hash FROM clienttask WHERE job_id=? ORDER BY hash",
                        (job_id,),
                    )
                ]
            return record

    def action(
        self,
        job_id: str,
        action: str,
        now: int,
        version: int | None = None,
        *,
        include_hashes: bool = True,
    ) -> dict:
        with closing(self.db()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT j.status,d.* FROM job j JOIN durable_request d ON j.id=d.job_id WHERE j.id=?",
                (job_id,),
            ).fetchone()
            if row is None:
                raise JobError("not_found", 404)
            if version is not None and row["version"] != version:
                raise JobError("version_conflict", 412)
            state = row["status"]
            target = state
            prior = row["prior_state"]
            if action == "cancel":
                target = (
                    "cancelled"
                    if state not in ("resolving", "downloading", "cancelling")
                    else "cancelling"
                )
            elif action == "pause" and state not in (
                "completed",
                "cancelled",
                "cancelling",
                "paused",
            ):
                target, prior = "paused", state
            elif action == "resume" and state == "paused":
                target = prior if prior in ("blocked", "failed") else "queued"
            elif action == "retry":
                if (
                    state not in ("blocked", "failed")
                    or row["error_code"] == "legacy_request_incomplete"
                ):
                    raise JobError("invalid_state", 409)
                if row["last_retry_at"] is not None and now - row["last_retry_at"] < 60:
                    raise JobError("rate_limited", 429)
                target = "queued"
                db.execute(
                    "UPDATE durable_request SET attempts=0,error_code=NULL,next_retry_at=NULL,last_retry_at=? WHERE job_id=?",
                    (now, job_id),
                )
            elif action not in ("pause", "resume"):
                raise JobError("invalid_request", 400)
            if target != state:
                db.execute(
                    "UPDATE job SET status=?,speed=0,updated_at=? WHERE id=?",
                    (target, timestamp(now), job_id),
                )
                # Generation invalidates callbacks already in flight before desired state changed.
                db.execute(
                    "UPDATE durable_request SET version=version+1,generation=generation+1,prior_state=?,lease_until=0 WHERE job_id=?",
                    (prior, job_id),
                )
        return self.get(job_id, include_hashes=include_hashes)

    def claim(self, now: int) -> dict | None:
        with closing(self.db()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT j.id,j.source_site,d.* FROM job j JOIN durable_request d ON j.id=d.job_id WHERE (j.status='queued' OR (j.status='retry_wait' AND d.next_retry_at<=?)) ORDER BY j.created_at,j.id LIMIT 1",
                (now,),
            ).fetchone()
            if row is None:
                return None
            if row["source_site"] not in self.providers:
                db.execute(
                    "UPDATE job SET status='paused',message='disabled_provider' WHERE id=?",
                    (row["id"],),
                )
                db.execute(
                    "UPDATE durable_request SET error_code='disabled_provider',version=version+1 WHERE job_id=?",
                    (row["id"],),
                )
                return None
            db.execute(
                "UPDATE job SET status='resolving',updated_at=? WHERE id=?",
                (timestamp(now), row["id"]),
            )
            db.execute(
                "UPDATE durable_request SET attempts=attempts+1,lease_until=?,last_attempt_at=?,version=version+1,generation=generation+1 WHERE job_id=?",
                (now + 60, now, row["id"]),
            )
            return {**dict(row), "generation": row["generation"] + 1}

    def finish(
        self,
        job_id: str,
        generation: int,
        outcome: str,
        now: int,
        output: Path | None = None,
        evidence: dict | None = None,
    ) -> bool:
        with closing(self.db()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT j.status,d.* FROM job j JOIN durable_request d ON d.job_id=j.id WHERE j.id=?",
                (job_id,),
            ).fetchone()
            if (
                row is None
                or row["generation"] != generation
                or row["status"] not in ("resolving", "downloading")
            ):
                return False
            retry = None
            code = outcome
            if outcome == "ok":
                require(
                    output is not None
                    and output.resolve().is_relative_to(self.download_dir)
                    and output.is_file(),
                    "invalid completed output",
                )
                with output.open("rb") as stream:
                    import os

                    os.fsync(stream.fileno())
                fsync_directory(output.parent)
                state, code = "completed", None
            elif outcome == "challenge":
                state = "blocked"
            elif outcome == "transport_failure" and row["attempts"] < 3:
                state, retry = "retry_wait", now + (60 if row["attempts"] == 1 else 300)
            else:
                state = "failed"
                if outcome == "transport_failure":
                    code = "retry_exhausted"
            db.execute(
                "UPDATE job SET status=?,progress=CASE WHEN ?=100 THEN 100 ELSE min(progress,99.9) END,result_path=?,speed=0,message=?,updated_at=? WHERE id=?",
                (
                    state,
                    100 if state == "completed" else 0,
                    str(output) if state == "completed" else None,
                    code,
                    timestamp(now),
                    job_id,
                ),
            )
            db.execute(
                "UPDATE durable_request SET error_code=?,next_retry_at=?,lease_until=0,version=version+1 WHERE job_id=?",
                (code, retry, job_id),
            )
            if state == "completed":
                frozen = json.loads(row["payload"])
                if (
                    frozen.get("mode") == "strm"
                    and frozen.get("strm_delivery") == "proxy"
                ):
                    # Imported STRM files outlive download-client removal. Bind
                    # playback registration to this proven completed request in
                    # the same transaction, independently of later alias state.
                    import hashlib

                    db.execute(
                        "INSERT OR REPLACE INTO catalog_cache VALUES('strm_proxy',?,?,?,?)",
                        (
                            job_id,
                            json.dumps(
                                {
                                    "payload_digest": hashlib.sha256(
                                        row["payload"].encode()
                                    ).hexdigest()
                                },
                                separators=(",", ":"),
                            ),
                            2**63 - 1,
                            now,
                        ),
                    )
                db.execute(
                    "UPDATE clienttask SET completion_on=? WHERE job_id=?",
                    (timestamp(now), job_id),
                )
                if evidence and writable(self.filename, self.metadata_limit, 4096):
                    retain_quality(
                        db, job_id, json.loads(row["payload"]), evidence, now
                    )
            return True

    def heartbeat(
        self, job_id: str, generation: int, now: int, progress: dict | None = None
    ) -> bool:
        with closing(self.db()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT j.status,d.generation,d.lease_until FROM job j JOIN durable_request d ON j.id=d.job_id WHERE j.id=?",
                (job_id,),
            ).fetchone()
            if (
                row is None
                or row["generation"] != generation
                or row["status"] not in ("resolving", "downloading")
            ):
                return False
            if progress is None and row["lease_until"] > now + 50:
                return True
            db.execute(
                "UPDATE durable_request SET lease_until=? WHERE job_id=?",
                (now + 60, job_id),
            )
            if progress is not None:
                downloaded = max(0, int(progress.get("downloaded_bytes") or 0))
                total = progress.get("total_bytes")
                total = int(total) if total is not None and int(total) > 0 else None
                percentage = min(99.9, downloaded * 100 / total) if total else 0
                db.execute(
                    "UPDATE job SET status='downloading',downloaded_bytes=?,total_bytes=?,progress=?,speed=?,eta=?,updated_at=? WHERE id=?",
                    (
                        downloaded,
                        total,
                        percentage,
                        max(0, float(progress.get("speed") or 0)),
                        progress.get("eta"),
                        timestamp(now),
                        job_id,
                    ),
                )
            return True

    def settle_cancel(self, job_id: str, now: int) -> None:
        with closing(self.db()) as db, db:
            changed = db.execute(
                "UPDATE job SET status='cancelled',speed=0,updated_at=? WHERE id=? AND status='cancelling'",
                (timestamp(now), job_id),
            ).rowcount
            if changed:
                db.execute(
                    "UPDATE durable_request SET version=version+1,lease_until=0 WHERE job_id=?",
                    (job_id,),
                )

    def recover(self, now: int, startup: bool = False) -> None:
        # Release each reader before CAS recovery writes. Keyset batches keep
        # both Python retention and write transactions independent of history.
        after = ""
        while True:
            with closing(self.db()) as db:
                rows = db.execute(
                    "SELECT j.id,d.generation FROM job j JOIN durable_request d ON j.id=d.job_id "
                    "WHERE j.id>? AND j.status IN ('resolving','downloading') "
                    "AND (d.lease_until<=? OR ?) ORDER BY j.id LIMIT 100",
                    (after, now, startup),
                ).fetchall()
            if not rows:
                break
            after = rows[-1]["id"]
            for row in rows:
                self.finish(row["id"], row["generation"], "transport_failure", now)
        with closing(self.db()) as db, db:
            if startup:
                db.execute(
                    "UPDATE job SET status='cancelled',speed=0 WHERE status='cancelling' AND id IN (SELECT job_id FROM durable_request)"
                )
        after = ""
        while True:
            with closing(self.db()) as db:
                rows = db.execute(
                    "SELECT id,result_path FROM job WHERE id>? AND status='completed' ORDER BY id LIMIT 100",
                    (after,),
                ).fetchall()
            if not rows:
                break
            after = rows[-1]["id"]
            for row in rows:
                if row["result_path"] and Path(row["result_path"]).is_file():
                    continue
                with closing(self.db()) as db, db:
                    # Do not overwrite a cancellation that raced the file check.
                    changed = db.execute(
                        "UPDATE job SET status='failed',message='missing_output',speed=0 WHERE id=? AND status='completed' AND result_path IS ?",
                        (row["id"], row["result_path"]),
                    ).rowcount
                    if changed:
                        db.execute(
                            "UPDATE durable_request SET error_code='missing_output',version=version+1 WHERE job_id=?",
                            (row["id"],),
                        )

    def projection(self, job_id: str) -> dict:
        return self.project(self.get(job_id))

    def iter_retained_directories(self) -> Iterator[Path]:
        """Stream durable ownership; legacy destinations stay conservative."""
        with closing(self.db()) as db:
            for row in db.execute(
                "SELECT j.id,d.payload FROM job j JOIN durable_request d ON d.job_id=j.id WHERE j.status!='completed'"
            ):
                payload = json.loads(row["payload"])
                if payload.get("legacy"):
                    destination = payload.get("save_path")
                    yield (
                        Path(destination).resolve()
                        if destination
                        else self.download_dir
                    )
                else:
                    yield output_paths(payload, row["id"])[0]

    def retained_directories(self) -> set[Path]:
        """Compatibility helper; the runtime uses the disk-backed TTL guard."""
        return set(self.iter_retained_directories())

    def retained_directory_guard(self) -> AbstractContextManager[DirectoryGuard]:
        return directory_guard(self.iter_retained_directories())

    @staticmethod
    def project(row: dict) -> dict:
        complete = row["status"] == "completed"
        progress = 1.0 if complete else min(0.999, max(0, (row["progress"] or 0) / 100))
        return {
            "state": QBIT.get(row["status"], "error"),
            "progress": progress,
            "size": row["total_bytes"] or 0,
            "dlspeed": int(row["speed"] or 0) if row["status"] == "downloading" else 0,
            "eta": int(row["eta"])
            if row["eta"] is not None and row["status"] == "downloading"
            else 8640000,
            "content_path": row["result_path"] if complete else "",
            "completion_on": row["updated_at"] if complete else None,
        }
