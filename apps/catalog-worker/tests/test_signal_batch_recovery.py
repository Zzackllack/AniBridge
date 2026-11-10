"""Season refreshes must finish recent obligations without postponing them."""

import json

import pytest
from catalog_core.providers.aniworld import EpisodeRow
from test_signals import EP, NOW, TITLE, accept, prepared

from catalog_worker.aniworld import Link, Page
from catalog_worker.signals import Signals
from catalog_worker.state import State


@pytest.mark.parametrize("supplied", [True, False])
def test_season_refresh_settles_or_preserves_pending_hint(tmp_path, supplied):
    state = prepared(tmp_path)
    try:
        before = tuple(state.db.execute("SELECT * FROM release").fetchone())
        accept(state, [(EP, "Example", "en-sub")])
        season = TITLE + "/staffel-1"
        page = Page(
            (Link(EP, "One"),),
            (),
            0,
            None,
            episodes=(
                EpisodeRow(
                    EP,
                    "One",
                    (),
                    ("de-dub", "en-sub") if supplied else ("de-dub",),
                ),
            ),
        )
        # Establish an unchanged season row. A second refresh used to overwrite
        # the targeted episode's due clock with the seven-day fallback.
        parent = dict(
            state.db.execute("SELECT * FROM work WHERE path=?", (season,)).fetchone()
        )
        state.detail(parent, page, NOW + 2)
        state.detail(parent, page, NOW + 3)
        state.close()
        state = State(tmp_path / "worker.sqlite", "aniworld.to")
        if supplied:
            assert Signals(state).status()["pending"] == 0
            assert (
                state.db.execute("SELECT due FROM work WHERE path=?", (EP,)).fetchone()[
                    0
                ]
                > NOW + 3
            )
        else:
            hint = state.db.execute("SELECT * FROM signal_pending").fetchone()
            assert json.loads(hint["expected"]) == ["en-sub"]
            work = state.claim(hint["due"], incremental=True)
            assert work["path"] == EP and work["targeted"]
            assert hint["due"] < NOW + 3600
        assert (
            tuple(
                state.db.execute(
                    "SELECT * FROM release WHERE release_id=?", (before[0],)
                ).fetchone()
            )[:4]
            == before[:4]
        )
    finally:
        state.close()


def test_missing_advertised_language_backs_off_and_recovers_after_restart(tmp_path):
    state = prepared(tmp_path)
    try:
        accept(state, [(EP, "Example", "en-sub")])
        now = NOW + 1
        delays = []
        for _ in range(9):
            with state.db:
                work = Signals(state).claim(now, 0, 120, 604800, 1200)
            assert work["path"] == EP and work["targeted"]
            state.detail(work, Page((), ("de-dub",), 0, None, episode_title="One"), now)
            Signals(state).settle(work, now, success=True)
            due = state.db.execute("SELECT due FROM signal_pending").fetchone()[0]
            delays.append(due - now)
            state.close()
            state = State(tmp_path / "worker.sqlite", "aniworld.to")
            assert (
                state.db.execute("SELECT due FROM work WHERE path=?", (EP,)).fetchone()[
                    0
                ]
                == due
            )
            now = due
        assert delays == [60, 120, 240, 480, 960, 1920, 3600, 3600, 3600]
        assert state.db.execute("SELECT count(*) FROM release").fetchone()[0] == 1
        with state.db:
            work = Signals(state).claim(now, 0, 120, 604800, 1200)
        state.detail(
            work,
            Page((), ("de-dub", "en-sub"), 0, None, episode_title="One"),
            now,
        )
        Signals(state).settle(work, now, success=True)
        assert Signals(state).status()["pending"] == 0
        assert state.db.execute("SELECT count(*) FROM release").fetchone()[0] == 2
    finally:
        state.close()


def test_season_evidence_keeps_a_failed_detail_retry_and_its_receipt(tmp_path):
    state = prepared(tmp_path)
    try:
        accept(state, [(EP, "Example", "en-sub")])
        work = state.claim(NOW + 1, incremental=True)
        state.failure(work, "transport_failure", NOW + 1, status=500)
        Signals(state).settle(work, NOW + 1, success=False)
        retry = tuple(
            state.db.execute(
                "SELECT due,failures,checked_at FROM work WHERE path=?", (EP,)
            ).fetchone()
        )
        receipt = tuple(state.db.execute("SELECT * FROM work_failure").fetchone())
        season = TITLE + "/staffel-1"
        state.detail(
            dict(
                state.db.execute(
                    "SELECT * FROM work WHERE path=?", (season,)
                ).fetchone()
            ),
            Page(
                (Link(EP, "One"),),
                (),
                0,
                None,
                episodes=(EpisodeRow(EP, "One", (), ("de-dub", "en-sub")),),
            ),
            NOW + 2,
        )
        assert Signals(state).status()["pending"] == 1
        assert (
            tuple(
                state.db.execute(
                    "SELECT due,failures,checked_at FROM work WHERE path=?", (EP,)
                ).fetchone()
            )
            == retry
        )
        assert (
            tuple(state.db.execute("SELECT * FROM work_failure").fetchone()) == receipt
        )
    finally:
        state.close()
