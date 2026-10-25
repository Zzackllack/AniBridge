"""Local movie player selection; no original-language or default-German guess."""

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.hosts import detect_host

LABELS = {
    "Deutsch": "de-dub",
    "German Dub": "de-dub",
    "English Dub": "en-dub",
    "German Sub": "de-sub",
    "English Sub": "en-sub",
}


def offers(html: str, origin: str, language: str) -> dict[str, str]:
    """Select only a recognised host attached to an explicit player language."""
    soup = BeautifulSoup(html, "html.parser")
    found = {}
    for node in soup.select(
        "iframe[data-language-label], a[data-language-label], button[data-language-label]"
    ):
        if LABELS.get(node.get("data-language-label")) != language:
            continue
        attributes = (
            ("src", "data-src")
            if node.name == "iframe"
            else ("data-iframe", "data-embed", "data-player")
        )
        target = next((node.get(key) for key in attributes if node.get(key)), None)
        if not target:
            continue
        url = urljoin(origin, target)
        host = detect_host(url)
        if host and host.name not in found:
            found[host.name] = url
    return found
