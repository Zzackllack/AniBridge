"""A failed native control must not be reported as successful diagnostics."""

from types import SimpleNamespace

import pytest


def probe_with_results(monkeypatch, failed_limit):
    pytest.importorskip("resource")
    from scripts.catalog.query_pilot import media_limit_probe as probe

    monkeypatch.setattr(probe, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(
        probe, "subprocess", SimpleNamespace(run=lambda *args, **kwargs: None)
    )
    monkeypatch.setattr(
        probe,
        "phase",
        lambda root, operation, memory: {
            "operation": operation,
            "address_limit_mib": memory,
            "exit_code": 1 if memory == failed_limit or memory == 256 else 0,
        },
    )
    return probe


@pytest.mark.parametrize("failed_limit", [320, 512])
def test_probe_fails_when_a_supported_control_fails(monkeypatch, failed_limit):
    probe = probe_with_results(monkeypatch, failed_limit)
    with pytest.raises(SystemExit) as error:
        probe.main()
    assert error.value.code == 1


def test_old_reference_limit_may_fail_without_hiding_supported_controls(monkeypatch):
    probe = probe_with_results(monkeypatch, None)
    probe.main()
