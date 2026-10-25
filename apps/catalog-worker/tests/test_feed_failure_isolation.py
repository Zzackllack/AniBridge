"""A failing capped recent feed must not postpone independent inventory work."""

import pytest
from test_pipeline import NOW, collectors

from catalog_worker.collector import Plan, Ready
from catalog_worker.signals import Signals


@pytest.mark.parametrize(
    "outcome,status", [("http_error", 500), ("unexpected_structure", 200)]
)
def test_failed_recent_feed_leaves_inventory_due_and_gap_latched(
    tmp_path, outcome, status
):
    group = collectors(tmp_path)
    collector = group[0]
    state = collector.state
    try:
        with state.db:
            state.db.execute("UPDATE worker_meta SET next_listing=?", (NOW,))
            state.db.execute("UPDATE signal_meta SET next_due=?", (NOW,))
        plan = collector.prepare()
        assert plan.signal and not plan.listing
        collector.apply(Ready(plan, None, outcome, status=status))
        assert state.meta()["next_listing"] == NOW
        assert Signals(state).status()["coverage"] == "gap"
        assert Signals(state).status()["next_due"] == NOW + 900
        next_plan = collector.prepare()
        assert next_plan.listing and not next_plan.signal
    finally:
        for item in group:
            item.state.close()


@pytest.mark.parametrize("targeted", [False, True])
def test_failed_observation_and_signal_retry_share_one_checkpoint(
    tmp_path, monkeypatch, targeted
):
    group = collectors(tmp_path)
    collector = group[0]
    state = collector.state
    try:
        if targeted:
            work = state.claim(NOW)
            Signals(state).enqueue(work["path"], work["title_id"], work["kind"], NOW)
            state.db.commit()
            work["signal_generation"] = state.db.execute(
                "SELECT generation FROM signal_pending"
            ).fetchone()[0]
            plan = Plan(NOW, False, work, work["path"])
            method = "settle"
        else:
            with state.db:
                state.db.execute("UPDATE signal_meta SET next_due=?", (NOW,))
            plan = collector.prepare()
            assert plan.signal
            method = "failed"
        tables = (
            "worker_meta",
            "work",
            "work_failure",
            "signal_meta",
            "signal_pending",
        )
        before = {t: list(state.db.execute(f"SELECT * FROM {t}")) for t in tables}
        original = getattr(Signals, method)

        def interrupted(self, *args, **kwargs):
            original(self, *args, **kwargs)
            raise RuntimeError("injected failed checkpoint")

        monkeypatch.setattr(Signals, method, interrupted)
        with pytest.raises(RuntimeError, match="checkpoint"):
            collector.apply(Ready(plan, None, "http_error", status=500))
        for table, rows in before.items():
            assert list(state.db.execute(f"SELECT * FROM {table}")) == rows, table
    finally:
        for item in group:
            item.state.close()
