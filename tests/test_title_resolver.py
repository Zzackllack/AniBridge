def test_build_index_from_html():
    from app.utils.title_resolver import build_index_from_html

    html = """
    <html><body>
    <a href="/anime/stream/slug-one">Title One</a>
    <a href="/anime/stream/slug-two">Title Two</a>
    </body></html>
    """
    index = build_index_from_html(html)
    assert index == {"slug-one": "Title One", "slug-two": "Title Two"}
