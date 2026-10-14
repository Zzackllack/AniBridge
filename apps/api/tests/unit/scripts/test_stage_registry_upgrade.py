"""Image/config preparation cannot silently move volumes, routes or resources."""

import importlib.util
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[5]
SPEC = importlib.util.spec_from_file_location(
    "registry_stage", ROOT / "scripts/catalog/query_pilot/stage_registry_upgrade.py"
)
STAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STAGE)


def fixture():
    before = yaml.safe_load(
        (ROOT / "scripts/catalog/query_pilot/server.yaml").read_text()
    )
    before["x-worker"]["image"] = STAGE.OLD_WORKER
    for service in before["services"].values():
        service["image"] = STAGE.OLD_WORKER
        service["pull_policy"] = "missing"
    before["services"]["collector"]["mem_limit"] = "2g"
    before["services"]["collector"]["memswap_limit"] = "2g"
    return {
        "uuid": STAGE.SERVICE,
        "docker_compose_raw": yaml.safe_dump(before, sort_keys=False),
    }


def test_registry_stage_preserves_original_bytes_and_all_unrelated_fields():
    service = fixture()
    worker = {
        "canonical_sources": {"tv": "skyhook", "movie": "off"},
        "providers": {"s.to": "https://serienstream.to"},
        "limits": {"total_disk_bytes": 30000000000},
    }
    image = "ghcr.io/zzackllack/anibridge-catalog-worker-preview@sha256:" + "a" * 64
    candidate, rollback, new_worker, old_worker = STAGE.prepare(service, worker, image)
    before = yaml.safe_load(rollback)
    after = yaml.safe_load(candidate)
    assert rollback == service["docker_compose_raw"] and old_worker == worker
    for name in ("initialize", "collector", "metadata"):
        assert after["services"][name]["image"] == image
        after["services"][name]["image"] = STAGE.OLD_WORKER
    after["x-worker"]["image"] = STAGE.OLD_WORKER
    assert after == before
    assert new_worker["canonical_sources"].pop("episode_languages") == ["deu"]
    assert new_worker == worker


def test_registry_stage_refuses_new_config_on_old_worker():
    with pytest.raises(ValueError, match="tested new worker"):
        STAGE.prepare(fixture(), {"canonical_sources": {}}, STAGE.OLD_WORKER)


@pytest.mark.parametrize("change", ["image", "memory", "policy", "service"])
def test_registry_stage_refuses_drift_or_mutable_refs(change):
    service = fixture()
    raw = yaml.safe_load(service["docker_compose_raw"])
    if change == "image":
        raw["services"]["metadata"]["image"] = "unexpected"
    elif change == "memory":
        raw["services"]["collector"]["mem_limit"] = "4g"
    elif change == "policy":
        raw["services"]["metadata"]["pull_policy"] = "always"
    else:
        service["uuid"] = "unrelated"
    service["docker_compose_raw"] = yaml.safe_dump(raw)
    with pytest.raises(ValueError):
        STAGE.prepare(
            service,
            {"canonical_sources": {}},
            "ghcr.io/zzackllack/anibridge-catalog-worker-preview@sha256:" + "a" * 64,
        )
    with pytest.raises(ValueError):
        STAGE.prepare(
            fixture(),
            {"canonical_sources": {}},
            "ghcr.io/zzackllack/anibridge-catalog-worker-preview:pr-170",
        )
