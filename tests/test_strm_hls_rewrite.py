from app.core.strm_proxy.hls import (
    build_synthetic_master_playlist,
    inject_stream_inf_bandwidth_hints,
    is_hls_media_playlist,
    rewrite_hls_playlist,
)


def _proxy_rewrite(u: str) -> str:
    """
    Prefix the given URL with the proxy scheme.

    Parameters:
        u (str): The original URL to rewrite.

    Returns:
        str: The URL prefixed with "proxy://".
    """
    return f"proxy://{u}"


def test_rewrite_hls_master_playlist():
    playlist = (
        "#EXTM3U\n"
        "#EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=640x360\n"
        "low/playlist.m3u8\n"
        "#EXT-X-STREAM-INF:BANDWIDTH=1400000,RESOLUTION=1280x720\n"
        "https://cdn.example.com/high/playlist.m3u8\n"
        '#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio",NAME="English",URI="audio/eng/playlist.m3u8"\n'
    )
    base_url = "https://origin.example/dir/master.m3u8"

    rewritten = rewrite_hls_playlist(
        playlist, base_url=base_url, rewrite_url=_proxy_rewrite
    )

    assert "proxy://https://origin.example/dir/low/playlist.m3u8" in rewritten
    assert "proxy://https://cdn.example.com/high/playlist.m3u8" in rewritten
    assert (
        'URI="proxy://https://origin.example/dir/audio/eng/playlist.m3u8"' in rewritten
    )


def test_rewrite_hls_media_playlist_with_key_and_map():
    playlist = (
        "#EXTM3U\n"
        "#EXT-X-VERSION:7\n"
        '#EXT-X-MAP:URI="init.mp4"\n'
        '#EXT-X-KEY:METHOD=AES-128,URI="https://keys.example.com/key.bin"\n'
        "#EXTINF:6.0,\n"
        "segment001.m4s\n"
        "#EXTINF:6.0,\n"
        "segment002.m4s\n"
        "#EXT-X-ENDLIST\n"
    )
    base_url = "https://origin.example/media/playlist.m3u8"

    rewritten = rewrite_hls_playlist(
        playlist, base_url=base_url, rewrite_url=_proxy_rewrite
    )

    assert 'URI="proxy://https://origin.example/media/init.mp4"' in rewritten
    assert 'URI="proxy://https://keys.example.com/key.bin"' in rewritten
    assert "proxy://https://origin.example/media/segment001.m4s" in rewritten
    assert "proxy://https://origin.example/media/segment002.m4s" in rewritten


def test_rewrite_hls_master_playlist_preserves_bandwidth():
    playlist = (
        "#EXTM3U\n"
        "#EXT-X-STREAM-INF:BANDWIDTH=938338,RESOLUTION=1280x720\n"
        "video/playlist.m3u8\n"
    )
    base_url = "https://origin.example/master.m3u8"

    rewritten = rewrite_hls_playlist(
        playlist, base_url=base_url, rewrite_url=_proxy_rewrite
    )

    assert "#EXT-X-STREAM-INF:BANDWIDTH=938338,RESOLUTION=1280x720" in rewritten
    assert "proxy://https://origin.example/video/playlist.m3u8" in rewritten


def test_rewrite_hls_master_playlist_preserves_variant_metadata():
    playlist = (
        "#EXTM3U\n"
        "#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=938338,RESOLUTION=1280x720,"
        'FRAME-RATE=23.980,CODECS="avc1.4d4028,mp4a.40.2",VIDEO-RANGE=SDR\n'
        "index-f1-v1-a1.m3u8?t=token&sp=2500\n"
        "#EXT-X-I-FRAME-STREAM-INF:BANDWIDTH=185267,RESOLUTION=1280x720,"
        'CODECS="avc1.4d4028",URI="iframes-f1-v1-a1.m3u8?t=token&sp=2500",'
        "VIDEO-RANGE=SDR\n"
    )
    base_url = "https://origin.example/dir/master.m3u8"

    rewritten = rewrite_hls_playlist(
        playlist, base_url=base_url, rewrite_url=_proxy_rewrite
    )

    assert (
        "#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=938338,RESOLUTION=1280x720,"
        'FRAME-RATE=23.980,CODECS="avc1.4d4028,mp4a.40.2",VIDEO-RANGE=SDR' in rewritten
    )
    assert (
        "proxy://https://origin.example/dir/index-f1-v1-a1.m3u8?t=token&sp=2500"
        in rewritten
    )
    assert (
        "#EXT-X-I-FRAME-STREAM-INF:BANDWIDTH=185267,RESOLUTION=1280x720,"
        'CODECS="avc1.4d4028",'
        'URI="proxy://https://origin.example/dir/iframes-f1-v1-a1.m3u8?t=token&sp=2500",'
        "VIDEO-RANGE=SDR" in rewritten
    )


def test_rewrite_hls_uri_tags_v7_plus():
    playlist = (
        "#EXTM3U\n"
        '#EXT-X-PRELOAD-HINT:TYPE=PART,URI="part-1.0.ts"\n'
        '#EXT-X-RENDITION-REPORT:URI="rendition.m3u8",LAST-MSN=4,LAST-PART=0\n'
        '#EXT-X-SESSION-DATA:DATA-ID="com.example",URI="session.json"\n'
        '#EXT-X-SESSION-KEY:METHOD=AES-128,URI="keys/session.key"\n'
    )
    base_url = "https://origin.example/live/master.m3u8"

    rewritten = rewrite_hls_playlist(
        playlist, base_url=base_url, rewrite_url=_proxy_rewrite
    )

    assert 'URI="proxy://https://origin.example/live/part-1.0.ts"' in rewritten
    assert 'URI="proxy://https://origin.example/live/rendition.m3u8"' in rewritten
    assert 'URI="proxy://https://origin.example/live/session.json"' in rewritten
    assert 'URI="proxy://https://origin.example/live/keys/session.key"' in rewritten


def test_inject_stream_inf_bandwidth_hints_adds_average_when_missing():
    playlist = (
        "#EXTM3U\n"
        "#EXT-X-STREAM-INF:BANDWIDTH=1200000,RESOLUTION=1280x720\n"
        "video/main.m3u8\n"
    )

    rewritten = inject_stream_inf_bandwidth_hints(playlist, default_bandwidth=2_500_000)

    assert (
        "#EXT-X-STREAM-INF:BANDWIDTH=1200000,RESOLUTION=1280x720,AVERAGE-BANDWIDTH=1020000"
        in rewritten
    )


def test_inject_stream_inf_bandwidth_hints_adds_both_when_missing():
    playlist = (
        "#EXTM3U\n"
        '#EXT-X-STREAM-INF:RESOLUTION=1280x720,CODECS="avc1.4d401f,mp4a.40.2"\n'
        "video/main.m3u8\n"
    )

    rewritten = inject_stream_inf_bandwidth_hints(playlist, default_bandwidth=900000)

    assert (
        '#EXT-X-STREAM-INF:RESOLUTION=1280x720,CODECS="avc1.4d401f,mp4a.40.2",BANDWIDTH=900000,AVERAGE-BANDWIDTH=765000'
        in rewritten
    )


def test_is_hls_media_playlist():
    media_playlist = "#EXTM3U\n#EXTINF:6.0,\nseg-1.ts\n#EXT-X-ENDLIST\n"
    master_playlist = "#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=1000000\nvariant.m3u8\n"

    assert is_hls_media_playlist(media_playlist) is True
    assert is_hls_media_playlist(master_playlist) is False


def test_build_synthetic_master_playlist():
    playlist = build_synthetic_master_playlist(
        "https://example.test/playlist.m3u8",
        bandwidth=1_519_549,
    )

    assert playlist.startswith("#EXTM3U\n#EXT-X-VERSION:3\n")
    assert "BANDWIDTH=1519549" in playlist
    assert "AVERAGE-BANDWIDTH=1291616" in playlist
    assert "https://example.test/playlist.m3u8\n" in playlist
