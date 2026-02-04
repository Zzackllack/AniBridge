from app.core.strm_proxy.hls import rewrite_hls_playlist


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
    rewrite = lambda u: f"proxy://{u}"
    rewritten = rewrite_hls_playlist(playlist, base_url=base_url, rewrite_url=rewrite)

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
    rewrite = lambda u: f"proxy://{u}"
    rewritten = rewrite_hls_playlist(playlist, base_url=base_url, rewrite_url=rewrite)

    assert 'URI="proxy://https://origin.example/media/init.mp4"' in rewritten
    assert 'URI="proxy://https://keys.example.com/key.bin"' in rewritten
    assert "proxy://https://origin.example/media/segment001.m4s" in rewritten
    assert "proxy://https://origin.example/media/segment002.m4s" in rewritten
