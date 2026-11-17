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


def terminal_window(state):
    """Five bounded backoffs, then one terminal row with durable evidence."""
    accept(state, [(EP, "Example", "en-sub")])
    now = NOW + 1
    delays = []
    for _ in range(5):
        with state.db:
            work = Signals(state).claim(now, 0, 120, 604800, 1200)
        assert work["path"] == EP and work["targeted"]
        state.detail(work, Page((), ("de-dub",), 0, None, episode_title="One"), now)
        Signals(state).settle(work, now, success=True)
        hint = state.db.execute(
            "SELECT * FROM signal_pending WHERE path=?", (EP,)
        ).fetchone()
        assert hint["failures"] < 6
        delays.append(hint["due"] - now)
        now = hint["due"]
    with state.db:
        work = Signals(state).claim(now, 0, 120, 604800, 1200)
    assert work["path"] == EP and work["targeted"]
    state.detail(work, Page((), ("de-dub",), 0, None, episode_title="One"), now)
    Signals(state).settle(work, now, success=True)
    return now, delays


def test_missing_advertised_language_quarantines_with_durable_evidence(tmp_path):
    state = prepared(tmp_path)
    try:
        now, delays = terminal_window(state)
        assert delays == [60, 120, 240, 480, 960]
        status = Signals(state).status()
        assert status["pending"] == 0 and status["terminal_pending"] == 1
        assert status["quarantined"] == 1
        assert status["coverage"] == "gap" and status["gap_since"] is not None
        row = state.db.execute(
            "SELECT * FROM signal_pending WHERE path=?", (EP,)
        ).fetchone()
        assert row["failures"] == 6
        assert json.loads(row["expected"]) == ["en-sub"]
        generation = row["generation"]
        first_observed = row["first_observed"]
        anomaly = state.db.execute(
            "SELECT * FROM quarantine WHERE kind='signal'"
        ).fetchone()
        assert (anomaly["old_count"], anomaly["new_count"]) == (1, 1)
        assert (
            state.db.execute("SELECT due FROM work WHERE path=?", (EP,)).fetchone()[0]
            >= now + 86400
        )
        # Retained evidence: no language was invented while quarantined.
        assert state.db.execute("SELECT count(*) FROM release").fetchone()[0] == 1
        gap = state.db.execute(
            "SELECT * FROM observation_gap WHERE path=?", (EP,)
        ).fetchone()
        assert gap["unknown_languages"] == 1

        # Restart keeps the labels, generation, first observation and anomaly.
        state.close()
        state = State(tmp_path / "worker.sqlite", "aniworld.to")
        row = state.db.execute(
            "SELECT * FROM signal_pending WHERE path=?", (EP,)
        ).fetchone()
        assert row["failures"] == 6
        assert json.loads(row["expected"]) == ["en-sub"]
        assert (row["generation"], row["first_observed"]) == (
            generation,
            first_observed,
        )
        assert Signals(state).status()["terminal_pending"] == 1
        assert Signals(state).status()["quarantined"] == 1

        # The same advertisement falling back into the window is not new
        # evidence: do not reset the terminal row or resume polling.
        work_due = state.db.execute(
            "SELECT due FROM work WHERE path=?", (EP,)
        ).fetchone()[0]
        from catalog_core.identity import title_id

        tid = title_id(state.provider, TITLE)
        with state.db:
            Signals(state).enqueue(EP, tid, "episode", now + 10, "en-sub")
        stale = state.db.execute(
            "SELECT * FROM signal_pending WHERE path=?", (EP,)
        ).fetchone()
        assert (stale["failures"], stale["generation"]) == (6, generation)
        assert json.loads(stale["expected"]) == ["en-sub"]
        assert (
            state.db.execute("SELECT due FROM work WHERE path=?", (EP,)).fetchone()[0]
            == work_due
        )
        assert Signals(state).status()["quarantined"] == 1
        assert Signals(state).status()["pending"] == 0
    finally:
        state.close()


def test_fresh_expected_language_reopens_a_terminal_obligation(tmp_path):
    state = prepared(tmp_path)
    try:
        now, _ = terminal_window(state)
        original = state.db.execute(
            "SELECT generation,first_observed FROM signal_pending WHERE path=?", (EP,)
        ).fetchone()

        from catalog_core.identity import title_id

        tid = title_id(state.provider, TITLE)
        with state.db:
            Signals(state).enqueue(EP, tid, "episode", now + 10, "de-sub")
        reopened = state.db.execute(
            "SELECT * FROM signal_pending WHERE path=?", (EP,)
        ).fetchone()
        assert reopened["failures"] == 0
        assert json.loads(reopened["expected"]) == ["de-sub", "en-sub"]
        assert reopened["generation"] == original["generation"] + 1
        assert reopened["first_observed"] == original["first_observed"]
        assert (
            state.db.execute("SELECT due FROM work WHERE path=?", (EP,)).fetchone()[0]
            == now + 10
        )
        status = Signals(state).status()
        assert status["pending"] == 1 and status["terminal_pending"] == 0
        assert status["quarantined"] == 0

        with state.db:
            work = Signals(state).claim(now + 10, 0, 120, 604800, 1200)
        assert work["path"] == EP and work["targeted"]
        state.detail(
            work,
            Page((), ("de-dub", "en-sub", "de-sub"), 0, None, episode_title="One"),
            now + 10,
        )
        Signals(state).settle(work, now + 10, success=True)
        status = Signals(state).status()
        assert status["pending"] == 0 and status["terminal_pending"] == 0
        assert status["quarantined"] == 0
        # A resolved page does not claim the feed window is complete.
        assert status["coverage"] == "gap" and status["gap_since"] is not None
        assert state.db.execute("SELECT count(*) FROM release").fetchone()[0] == 3
    finally:
        state.close()


def test_repeated_active_advertisement_is_not_new_expectation_evidence(tmp_path):
    state = prepared(tmp_path)
    try:
        accept(state, [(EP, "Example", "en-sub")])
        original = state.db.execute(
            "SELECT * FROM signal_pending WHERE path=?", (EP,)
        ).fetchone()
        work_due = state.db.execute(
            "SELECT due FROM work WHERE path=?", (EP,)
        ).fetchone()[0]
        from catalog_core.identity import title_id

        tid = title_id(state.provider, TITLE)
        with state.db:
            Signals(state).enqueue(EP, tid, "episode", NOW + 30, "en-sub")
        stale = state.db.execute(
            "SELECT * FROM signal_pending WHERE path=?", (EP,)
        ).fetchone()
        assert (stale["generation"], stale["due"], stale["failures"]) == (
            original["generation"],
            original["due"],
            original["failures"],
        )
        assert (
            state.db.execute("SELECT due FROM work WHERE path=?", (EP,)).fetchone()[0]
            == work_due
        )
        # Only a genuinely new expected language advances the window.
        with state.db:
            Signals(state).enqueue(EP, tid, "episode", NOW + 31, "de-sub")
        changed = state.db.execute(
            "SELECT * FROM signal_pending WHERE path=?", (EP,)
        ).fetchone()
        assert changed["generation"] == original["generation"] + 1
        assert json.loads(changed["expected"]) == ["de-sub", "en-sub"]
    finally:
        state.close()


def test_terminal_obligation_clears_on_a_normal_historical_recheck(tmp_path):
    state = prepared(tmp_path)
    try:
        terminal_window(state)
        due = state.db.execute("SELECT due FROM work WHERE path=?", (EP,)).fetchone()[0]
        # A non-targeted historical claim has no signal generation. The normal
        # detail recheck can still resolve all expectations and clear terminal
        # evidence, but never an active hint (covered separately).
        work = dict(
            state.db.execute("SELECT * FROM work WHERE path=?", (EP,)).fetchone()
        )
        state.detail(
            work,
            Page((), ("de-dub", "en-sub"), 0, None, episode_title="One"),
            due,
        )
        Signals(state).settle(work, due, success=True)
        status = Signals(state).status()
        assert status["pending"] == 0 and status["terminal_pending"] == 0
        assert status["quarantined"] == 0
        # Coverage truth is not rewritten by one page.
        assert status["coverage"] == "gap" and status["gap_since"] is not None
        assert state.db.execute("SELECT count(*) FROM release").fetchone()[0] == 2
    finally:
        state.close()


def test_normal_recheck_cannot_consume_an_active_hint(tmp_path):
    state = prepared(tmp_path)
    try:
        accept(state, [(EP, "Example", "en-sub")])
        work = dict(
            state.db.execute("SELECT * FROM work WHERE path=?", (EP,)).fetchone()
        )
        now = NOW + 1
        state.detail(
            work, Page((), ("de-dub", "en-sub"), 0, None, episode_title="One"), now
        )
        Signals(state).settle(work, now, success=True)
        assert Signals(state).status()["pending"] == 1
        assert (
            state.db.execute(
                "SELECT failures FROM signal_pending WHERE path=?", (EP,)
            ).fetchone()[0]
            == 0
        )
    finally:
        state.close()


def test_terminal_rows_do_not_consume_the_cap_or_targeted_claims(tmp_path, monkeypatch):
    import catalog_worker.signals as module

    monkeypatch.setattr(module, "MAX_PENDING", 1)
    state = prepared(tmp_path)
    try:
        now, _ = terminal_window(state)
        assert Signals(state).status()["pending"] == 0
        from catalog_core.identity import title_id

        tid = title_id(state.provider, TITLE)
        second = EP.replace("episode-1", "episode-2")
        third = EP.replace("episode-1", "episode-3")
        with state.db:
            Signals(state).enqueue(second, tid, "episode", now + 1, "de-sub")
        assert Signals(state).status()["pending"] == 1
        assert Signals(state).status()["terminal_pending"] == 1
        # A terminal path must not steal the one active targeted slot.
        with state.db:
            work = Signals(state).claim(now + 1, 0, 120, 604800, 1200)
        assert work["path"] == second and work["targeted"]
        # The hard backstop still applies to active rows only.
        with state.db, pytest.raises(ValueError, match="pending overflow"):
            Signals(state).enqueue(third, tid, "episode", now + 1, "de-sub")
        assert Signals(state).status()["pending"] == 1
        # Reopening terminal work also needs an active slot. Preserve its
        # original evidence if the new language cannot yet be admitted.
        with pytest.raises(ValueError, match="pending overflow"), state.db:
            Signals(state).enqueue(EP, tid, "episode", now + 1, "de-sub")
        assert Signals(state).status()["pending"] == 1
        assert Signals(state).status()["terminal_pending"] == 1
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
