"""Incremental work survives restart without treating bounded hints as absences."""

import json

import pytest
from catalog_core import identity
from catalog_core.providers.recent import Change, Window
from catalog_worker.aniworld import Link, Page
from catalog_worker.signals import Signals
from catalog_worker.state import State

NOW = 1800000000
TITLE = "/anime/stream/example"
EP = TITLE + "/staffel-1/episode-1"
ORIGIN = "https://aniworld.to"


def prepared(tmp_path):
    state = State(tmp_path / "worker.sqlite", "aniworld.to")
    state.listing(Page((Link(TITLE, "Example"),), (), 0, None), NOW)
    state.detail(
        state.claim(NOW),
        Page((Link(TITLE + "/staffel-1", "Season"),), (), 0, "Example", year=2020),
        NOW,
    )
    state.detail(state.claim(NOW), Page((Link(EP, "One"),), (), 0, None), NOW)
    state.detail(
        state.claim(NOW), Page((), ("de-dub",), 0, None, episode_title="One"), NOW
    )
    return state


def accept(state, entries, now=NOW + 1, **options):
    Signals(state).accept(
        Window(
            tuple(Change(*r) for r in entries), **({"unknown_languages": 0} | options)
        ),
        now,
        900,
    )


def test_language_addition_only_fetches_episode_and_keeps_first_seen(tmp_path):
    state = prepared(tmp_path)
    before = tuple(state.db.execute("SELECT * FROM release").fetchone())
    accept(state, [(EP, "Example", "de-dub"), (EP, "Example", "en-sub")])
    work = state.claim(NOW + 1, incremental=True)
    assert work["path"] == EP and work["targeted"]
    state.detail(
        work, Page((), ("de-dub", "en-sub"), 0, None, episode_title="One"), NOW + 1
    )
    Signals(state).settle(work, NOW + 1, success=True)
    assert Signals(state).status()["pending"] == 0
    assert (
        state.db.execute(
            "SELECT first_seen_at FROM release WHERE language='de-dub'"
        ).fetchone()[0]
        == before[3]
    )
    assert (
        state.db.execute(
            "SELECT first_seen_at FROM release WHERE language='en-sub'"
        ).fetchone()[0]
        == NOW + 1
    )
    assert state.claim(NOW + 2, incremental=True) is None
    state.close()


def test_reordering_and_duplicates_do_not_reschedule_known_releases(tmp_path):
    state = prepared(tmp_path)
    accept(state, [(EP, "Example", "de-dub")])
    accept(state, [(EP, "Example", "de-dub")] * 2, NOW + 901)
    assert Signals(state).status()["pending"] == 0
    assert Signals(state).status()["coverage"] == "window-overlap"
    assert not state.db.execute("SELECT 1 FROM omissions").fetchone()
    state.close()


def test_new_title_fetches_only_targeted_parents_not_whole_series(tmp_path):
    state = prepared(tmp_path)
    title = "/anime/stream/new"
    episode = title + "/staffel-2/episode-9"
    accept(state, [(episode, "New title", "de-sub")])
    work = state.claim(NOW + 1, incremental=True)
    assert work["path"] == title
    state.detail(
        work,
        Page(
            (
                Link(title + "/staffel-2", "Season"),
                Link(title + "/staffel-1", "Old season"),
            ),
            (),
            0,
            "New title",
            year=2021,
        ),
        NOW + 1,
    )
    Signals(state).settle(work, NOW + 1, success=True)
    work = state.claim(NOW + 1, incremental=True)
    assert work["path"] == title + "/staffel-2"
    state.detail(
        work,
        Page(
            (Link(episode, "Nine"), Link(title + "/staffel-2/episode-8", "Eight")),
            (),
            0,
            None,
        ),
        NOW + 1,
    )
    Signals(state).settle(work, NOW + 1, success=True)
    assert state.claim(NOW + 1, incremental=True)["path"] == episode
    assert (
        state.db.execute(
            "SELECT count(*) FROM work WHERE title_id=?",
            (identity.title_id("aniworld.to", title),),
        ).fetchone()[0]
        == 5
    )
    assert state.db.execute("SELECT count(*) FROM omissions").fetchone()[0] == 0
    state.close()


@pytest.mark.parametrize(
    "case", ["overflow", "downtime", "empty", "unknown", "pagination"]
)
def test_incomplete_window_latches_gap_without_deletion(tmp_path, case):
    state = prepared(tmp_path)
    accept(state, [(EP, "Example", "de-dub")])
    now = NOW + 901
    options = {}
    rows = [(EP, "Example", "de-dub")]
    if case == "overflow":
        rows = [(EP.replace("episode-1", "episode-2"), "Example", "de-sub")]
    if case == "downtime":
        now = NOW + 86400
    if case == "empty":
        rows = []
    if case == "unknown":
        rows = [(EP, "Example", None)]
        options["unknown_languages"] = 1
    if case == "pagination":
        options["pagination"] = True
    accept(state, rows, now, **options)
    assert Signals(state).status()["coverage"] == "gap"
    assert Signals(state).status()["gap_since"] is not None
    accept(state, rows, now + 900, **options)
    assert Signals(state).status()["coverage"] == "gap"
    assert state.db.execute("SELECT count(*) FROM omissions").fetchone()[0] == 0
    assert state.db.execute("SELECT first_seen_at FROM release").fetchone()[0] == NOW
    state.close()


def test_restart_and_concurrent_new_hint_preserve_unsettled_generation(tmp_path):
    state = prepared(tmp_path)
    accept(state, [(EP, "Example", "en-sub")])
    work = state.claim(NOW + 1, incremental=True)
    accept(state, [(EP, "Example", "en-sub"), (EP, "Example", "de-sub")], NOW + 2)
    state.detail(
        work, Page((), ("de-dub", "en-sub"), 0, None, episode_title="One"), NOW + 2
    )
    Signals(state).settle(work, NOW + 2, success=True)
    state.close()
    state = State(tmp_path / "worker.sqlite", "aniworld.to")
    row = state.db.execute("SELECT * FROM signal_pending").fetchone()
    assert set(json.loads(row["expected"])) == {"en-sub", "de-sub"}
    assert Signals(state).status()["entries"] == 2
    state.close()


def test_missing_advertised_language_retries_without_invention(tmp_path):
    state = prepared(tmp_path)
    accept(state, [(EP, "Example", "en-sub")])
    work = state.claim(NOW + 1, incremental=True)
    state.detail(work, Page((), ("de-dub",), 0, None, episode_title="One"), NOW + 1)
    Signals(state).settle(work, NOW + 1, success=True)
    assert Signals(state).status()["pending"] == 1
    assert Signals(state).status()["coverage"] == "gap"
    assert state.claim(NOW + 2, incremental=True) is None
    assert state.db.execute("SELECT count(*) FROM release").fetchone()[0] == 1
    state.close()


def test_reconciliation_is_reserved_and_actual_starts_cannot_consume_headroom(tmp_path):
    state = prepared(tmp_path)
    with state.db:
        state.db.execute("UPDATE work SET checked_at=?,due=0", (NOW - 604801,))
        state.db.execute("UPDATE scheduler SET slot=4")
    accept(state, [(EP, "Example", "en-sub")])
    work = state.claim(NOW + 1, incremental=True)
    assert not work["targeted"]
    for n in range(4):
        assert state.allow_request(NOW + n * 2, 2, 20, reconciliation=True)
    assert not state.allow_request(NOW + 8, 2, 20, reconciliation=True)
    assert state.allow_request(NOW + 8, 2, 20)
    state.close()


def test_signal_poll_lease_provider_origin_and_cooldown_survive_restart(tmp_path):
    state = prepared(tmp_path)
    signals = Signals(state)
    assert signals.reserve(NOW, ORIGIN, 120)
    assert not signals.reserve(NOW + 119, ORIGIN, 120)
    state.close()
    state = State(tmp_path / "worker.sqlite", "aniworld.to")
    signals = Signals(state)
    assert signals.reserve(NOW + 120, ORIGIN, 120)
    accept(state, [(EP, "Example", "de-dub")], NOW + 120)
    assert not signals.reserve(NOW + 121, ORIGIN, 120)
    assert signals.reserve(NOW + 122, "https://other.invalid", 120)
    assert signals.status()["coverage"] == "unknown" and signals.status()["gap_since"]
    state.close()


def test_pending_overflow_rolls_back_window_and_work_atomically(tmp_path, monkeypatch):
    import catalog_worker.signals as module

    state = prepared(tmp_path)
    accept(state, [(EP, "Example", "de-dub")])
    before = Signals(state).status()
    monkeypatch.setattr(module, "MAX_PENDING", 1)
    with pytest.raises(ValueError, match="pending overflow"):
        accept(
            state,
            [("/anime/stream/new/staffel-1/episode-1", "New", "de-dub")],
            NOW + 901,
        )
    assert Signals(state).status() == before
    assert state.db.execute("SELECT count(*) FROM title").fetchone()[0] == 1
    state.close()


@pytest.mark.parametrize("point", ["pending", "window", "meta", "committed"])
def test_signal_checkpoint_sigkill_preserves_whole_old_or_new_observation(
    tmp_path, point
):
    import os
    import signal
    import sys

    if sys.platform != "linux":
        pytest.skip("actual Linux SIGKILL checkpoint")
    state = prepared(tmp_path)
    accept(state, [(EP, "Example", "de-dub")])
    state.close()
    child = os.fork()
    if child == 0:
        current = State(tmp_path / "worker.sqlite", "aniworld.to")
        needle = {
            "pending": "INSERT INTO signal_pending",
            "window": "DELETE FROM signal_window",
            "meta": "UPDATE signal_meta SET checked_at",
        }.get(point)

        def crash(sql):
            if needle and sql.startswith(needle):
                os.kill(os.getpid(), signal.SIGKILL)

        current.db.set_trace_callback(crash)
        accept(current, [(EP, "Example", "en-sub")], NOW + 901)
        os.kill(os.getpid(), signal.SIGKILL)
        os._exit(1)
    _, status = os.waitpid(child, 0)
    assert os.WIFSIGNALED(status) and os.WTERMSIG(status) == signal.SIGKILL
    state = State(tmp_path / "worker.sqlite", "aniworld.to")
    committed = point == "committed"
    assert Signals(state).status()["checked_at"] == (
        NOW + 901 if committed else NOW + 1
    )
    assert Signals(state).status()["pending"] == int(committed)
    assert state.db.execute("SELECT language FROM signal_window").fetchone()[0] == (
        "en-sub" if committed else "de-dub"
    )
    assert state.db.execute("SELECT first_seen_at FROM release").fetchone()[0] == NOW
    state.close()
