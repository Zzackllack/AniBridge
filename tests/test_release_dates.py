from datetime import datetime, timezone

from app.utils.release_dates import (
    add_release_at_to_probe_info,
    merge_extra_with_release_at,
    parse_release_at_from_html,
    parse_release_datetime_text,
    release_at_from_extra,
    release_at_from_probe_info,
)


def test_parse_release_datetime_text_german_with_time() -> None:
    """Parse German release strings with time to UTC."""
    parsed = parse_release_datetime_text("Freitag, 29.08.2025 18:46 Uhr")

    assert parsed == datetime(2025, 8, 29, 16, 46, tzinfo=timezone.utc)


def test_parse_release_at_from_html_sto_v2_like_markup() -> None:
    """Parse release datetime from STO v2-like HTML markup."""
    html_text = """
    <span class="flex-grow-1">
      <span title="Feb 23, 2026 20:47 Uhr">
        Veröffentlicht am February 23, 2026
      </span>
    </span>
    """

    parsed = parse_release_at_from_html(html_text)

    assert parsed == datetime(2026, 2, 23, 19, 47, tzinfo=timezone.utc)


def test_parse_release_at_from_html_ignores_invalid_year() -> None:
    """Return None for HTML with an invalid year."""
    html_text = """
    <span title="Nov 30, -0001 00:00">
      Published on November 30, -0001
    </span>
    """

    assert parse_release_at_from_html(html_text) is None


def test_release_at_roundtrip_via_extra_and_probe_info() -> None:
    """Roundtrip release_at through extra and probe info helpers."""
    release_at = datetime(2026, 2, 23, 19, 47, tzinfo=timezone.utc)
    extra = merge_extra_with_release_at(base_extra={"x": 1}, release_at=release_at)
    info = add_release_at_to_probe_info({}, release_at)

    assert extra is not None
    assert release_at_from_extra(extra) == release_at
    assert release_at_from_probe_info(info) == release_at
