"""Finite SQL/query/last-good checks on an explicitly disposable published copy."""

import argparse
import asyncio
import json
import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

import httpx
from catalog_core.json_codec import ContractError
from catalog_core.protocol import Request
from catalog_worker.config import load
from catalog_worker.query_server import create_app
from catalog_worker.read_catalog import provider_root, publish
from catalog_worker.state import State


async def verify(path: Path) -> dict:
    config = load(path)
    if not (config.state_dir / "COPY_ONLY").is_file():
        raise ValueError("disposable copy required")
    now = int(time.time())
    app = create_app(config.output_dir, "disposable-verification-token", now=now)
    result = {"queries": [], "last_good": {}}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://127.0.0.1",
        headers={"Authorization": "Bearer disposable-verification-token"},
    ) as http:

        async def query(req: Request, case: str, expected: int | None = None):
            begin = time.monotonic()
            response = await http.post("/catalog/v1/query", json=req.model_dump())
            body = response.json()
            item = {
                "case": case,
                "provider": req.provider,
                "status": response.status_code,
                "duration_s": round(time.monotonic() - begin, 6),
                "total": body.get("total"),
                "rows": len(body.get("rows", [])),
                "headers": body.get("headers", {}),
            }
            if expected is not None:
                assert response.status_code == 200 and body["total"] == expected
                item["sql_total"] = expected
            result["queries"].append(item)
            return body

        for provider in config.providers:
            root = provider_root(config.output_dir, provider)
            metadata = json.loads((root / "current.json").read_text())
            with sqlite3.connect(
                (root / metadata["database"]).as_uri() + "?mode=ro&immutable=1",
                uri=True,
            ) as db:
                for mode in ("search", "tvsearch"):
                    total = db.execute(
                        "SELECT count(*) FROM release r JOIN entity e USING(entity_id) WHERE r.first_seen_at>=?"
                        + (" AND e.kind='episode'" if mode == "tvsearch" else ""),
                        (now - 30 * 86400,),
                    ).fetchone()[0]
                    await query(
                        Request(
                            provider=provider,
                            operation="recent",
                            params={"t": mode},
                            limit=100,
                        ),
                        "recent_" + mode,
                        total,
                    )
                source = (
                    "/anime/stream/one-piece"
                    if provider == "aniworld.to"
                    else "/serie/breaking-bad"
                )
                title = db.execute(
                    "SELECT title_id FROM title WHERE identity_anchor=? OR path=?",
                    (source, source),
                ).fetchone()
                assert title
                coordinates = (
                    ((1, 1), (1, 6), (21, 14))
                    if provider == "aniworld.to"
                    else ((1, 1),)
                )
                for season, episode in coordinates:
                    expected = db.execute(
                        "SELECT count(*) FROM release r JOIN canonical_episode ce USING(entity_id) JOIN canonical_title ct USING(mapping_id) WHERE ct.title_id=? AND ct.namespace='tvdb' AND ce.season=? AND ce.episode=? AND r.first_seen_at>=?",
                        (title[0], season, episode, now - 30 * 86400),
                    ).fetchone()[0]
                    body = await query(
                        Request(
                            provider=provider,
                            operation="native",
                            params={"t": "search"},
                            title_ids=[title[0]],
                            season=season,
                            episode=episode,
                        ),
                        f"target_{season}_{episode}",
                        expected,
                    )
                    assert all(row["provider"] == provider for row in body["rows"])
                    assert (
                        expected
                        or body["headers"]["X-AniBridge-Mapping"] == "unresolved"
                    )
            pointer = (root / "current.json").read_bytes()
            state = State(config.state_dir / (provider + ".sqlite"), provider)
            try:
                with patch(
                    "catalog_worker.read_catalog.copy",
                    side_effect=ContractError("controlled fixture failure"),
                ):
                    try:
                        publish(config, state, now)
                    except ContractError:
                        pass
                    else:
                        raise AssertionError("failure expected")
                assert (root / "current.json").read_bytes() == pointer and not (
                    root / "staging.sqlite"
                ).exists()
                result["last_good"][provider] = True
            finally:
                state.close()
        # Removing one COPY pointer must not turn either provider into an empty success.
        pointer = config.output_dir / "current.json"
        saved = pointer.read_bytes()
        pointer.unlink()
        try:
            failed = await http.post(
                "/catalog/v1/query",
                json=Request(
                    provider="aniworld.to",
                    operation="recent",
                    params={"t": "search"},
                    limit=100,
                ).model_dump(),
            )
            isolated = await http.post(
                "/catalog/v1/query",
                json=Request(
                    provider="s.to",
                    operation="recent",
                    params={"t": "search"},
                    limit=100,
                ).model_dump(),
            )
            assert failed.status_code == 503 and isolated.status_code == 200
            result["provider_isolation"] = {
                "unavailable_status": 503,
                "other_provider_status": 200,
            }
        finally:
            pointer.write_bytes(saved)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(
        json.dumps(asyncio.run(verify(args.config)), indent=2) + "\n"
    )
