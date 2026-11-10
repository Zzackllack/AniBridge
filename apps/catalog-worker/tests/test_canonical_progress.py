"""Canonical retry age stays distinct from provider page failures."""

from catalog_worker import canonical_cache
from catalog_worker.progress import measure
from test_canonical import NOW
from test_matching_followup import seed


def test_status_separates_canonical_deadlines_from_page_failures(tmp_path):
    state, tid = seed(tmp_path)
    with state.db:
        canonical_cache.store(state, tid, "p", "m", NOW, [])
        state.db.execute(
            "UPDATE mapping_input SET checked_at=?,failures=2,next_due=?",
            (NOW - 600, NOW - 300),
        )
    result = measure(state.db, state.meta(), NOW)
    assert result["queue"]["failed_due_now"] == 0
    assert result["canonical_queue"] == {
        "never_checked": 0,
        "due_now": 1,
        "failed_due_now": 1,
        "cached_failed_due_now": 1,
        "oldest_due_age_s": 300,
        "oldest_failed_due_age_s": 300,
    }
    with state.db:
        state.db.execute(
            "UPDATE mapping_input SET checked_at=NULL,failures=0,next_due=0"
        )
    result = measure(state.db, state.meta(), NOW)["canonical_queue"]
    assert result["never_checked"] == result["due_now"] == 1
    assert result["oldest_due_age_s"] is None
    assert result["failed_due_now"] == result["cached_failed_due_now"] == 0
    assert measure(state.db, state.meta(), -1)["canonical_queue"]["due_now"] == 0
    state.close()
