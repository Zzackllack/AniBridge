from app.catalog.hls_size_estimate import (
    MAX_TRACKS,
    _content_length,
    _playlist_sample,
    _known_size,
    preflight_hls_track_sizes,
)
from app.catalog.media_transport import TransferState


def test_playlist_sample_counts_only_safe_finite_media_fragments():
    playlist = """#EXTM3U
#EXT-X-TARGETDURATION:6
#EXTINF:6,
first.ts
#EXTINF:6,
second.ts
#EXT-X-ENDLIST
"""

    assert _playlist_sample(playlist, "https://media.example/path/list.m3u8", {}) == (
        2,
        "https://media.example/path/first.ts",
    )


def test_playlist_sample_requires_endlist_as_a_standalone_tag():
    playlist = """#EXTM3U
#EXT-X-TARGETDURATION:6
#EXTINF:6,
segment.ts#EXT-X-ENDLIST
"""

    assert _playlist_sample(playlist, "https://media.example/list.m3u8", {}) is None


def test_playlist_sample_skips_ranges_maps_live_and_drm():
    for feature in (
        "#EXT-X-BYTERANGE:100@0",
        '#EXT-X-MAP:URI="init.mp4"',
        '#EXT-X-KEY:METHOD=AES-128,URI="key"',
        '#EXT-X-KEY:METHOD=SAMPLE-AES,URI="key"',
    ):
        playlist = (
            "#EXTM3U\n#EXT-X-TARGETDURATION:6\n"
            f"{feature}\n#EXTINF:6,\nsegment.ts\n#EXT-X-ENDLIST\n"
        )
        assert _playlist_sample(playlist, "https://media.example/list.m3u8", {}) is None

    live = "#EXTM3U\n#EXT-X-TARGETDURATION:6\n#EXTINF:6,\nsegment.ts\n"
    assert _playlist_sample(live, "https://media.example/list.m3u8", {}) is None


def test_invalid_or_preexisting_sizes_are_not_replaced():
    assert _content_length(None) is None
    assert _content_length("0") is None
    assert _content_length("-4") is None
    assert _content_length("4x") is None
    assert _content_length("40") == 40
    assert _known_size({"filesize": 90})
    assert _known_size({"filesize_approx": 90})
    assert not _known_size({"filesize_approx": 0})


def test_track_count_bound_skips_all_optional_requests(tmp_path):
    class NoRequests:
        def urlopen(self, request):
            raise AssertionError("preflight exceeded the selected-track bound")

    items = [
        {"protocol": "m3u8_native", "url": f"https://media.example/{i}.m3u8"}
        for i in range(MAX_TRACKS + 1)
    ]
    state = TransferState(tmp_path)

    preflight_hls_track_sizes(items, NoRequests(), state)

    assert all("filesize_approx" not in item for item in items)
    assert state.error is None and state.timeout_s == 120 and state.deadline_s is None
