"""Create explicit private server/client configuration on an operator's machine."""

import argparse
import json
import secrets
from pathlib import Path
from urllib.parse import urlsplit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--metadata-origin", required=True)
    parser.add_argument("--source-id", default="private-linux-pilot")
    parser.add_argument("--aniworld-origin", default="https://aniworld.to")
    parser.add_argument("--serienstream-origin", default="https://serienstream.to")
    parser.add_argument("--megakino-origin")
    parser.add_argument("--megakino-sitemap-origin", action="append", default=[])
    args = parser.parse_args()
    origins = {"aniworld.to": args.aniworld_origin, "s.to": args.serienstream_origin}
    if args.megakino_origin:
        origins["megakino"] = args.megakino_origin
    for origin in [
        args.metadata_origin,
        *origins.values(),
        *args.megakino_sitemap_origin,
    ]:
        url = urlsplit(origin)
        if (
            url.scheme != "https"
            or not url.hostname
            or url.path not in ("", "/")
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            parser.error("select verified HTTPS origins without paths or credentials")
    root = args.directory.resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if any(root.iterdir()):
        parser.error(
            "configuration directory must be empty; existing credentials are never replaced"
        )
    worker = {
        "providers": origins,
        "canonical_sources": {"tv": "skyhook", "movie": "off", "episode_languages": ["deu"]},
        "state_dir": "/state",
        "output_dir": "/read",
        "source_id": args.source_id,
        "publication_sources": ["skyhook-v1"],
        "limits": {"publish_interval_s": 300},
    }
    if args.megakino_sitemap_origin:
        worker["sitemap_origins"] = {"megakino": args.megakino_sitemap_origin}
    client = {
        "mode": "query",
        "origin": args.metadata_origin,
        "source_id": args.source_id,
        "token_file": "/config/metadata-token",
    }
    for name, body in (
        ("worker.json", json.dumps(worker, indent=2)),
        ("client.json", json.dumps(client, indent=2)),
        ("metadata-token", secrets.token_urlsafe(32)),
    ):
        path = root / name
        path.write_text(body + "\n")
        path.chmod(0o600)
    print(
        "Prepared worker.json, client.json and metadata-token. Compose initializes private container ownership separately."
    )


if __name__ == "__main__":
    main()
