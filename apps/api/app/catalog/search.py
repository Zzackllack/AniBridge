"""User-local RSS formatting over shared metadata contracts."""

import xml.etree.ElementTree as ET
from email.utils import formatdate
from catalog_core import identity, magnet
from catalog_core.query import LANGUAGES, TORZNAB, NEWZNAB
from catalog_core.query import parse as parse


def rss(rows: list[dict], total: int, offset: int) -> bytes:
    # Prefix declarations belong to this document. register_namespace changes
    # process-global serializer state and breaks the legacy feed's declarations.
    root = ET.Element(
        "rss", {"version": "2.0", "xmlns:torznab": TORZNAB, "xmlns:newznab": NEWZNAB}
    )
    channel = ET.SubElement(root, "channel")
    ET.SubElement(channel, "title").text = "AniBridge"
    ET.SubElement(channel, "description").text = "Local catalog releases"
    ET.SubElement(channel, "link").text = "http://localhost/"
    ET.SubElement(
        channel, "newznab:response", {"offset": str(offset), "total": str(total)}
    )
    for row in rows:
        payload = {key: row[key] for key in magnet.PAYLOAD_FIELDS - {"canonical"}}
        canonical = None
        if row["namespace"] and (row["kind"] == "movie" or row["season"] is not None):
            canonical = {
                key: row[key]
                for key in ("namespace", "external_id", "season", "episode")
            }
        payload["canonical"] = canonical
        label = row["display_title"]
        if row["kind"] == "movie" and row.get("year") is not None:
            # Radarr's release parser needs the observed movie year. This is
            # display metadata only; correcting it must not change identity.
            label += f".{row['year']}"
        if row["kind"] == "episode":
            season = (
                row["season"] if row["season"] is not None else row["native_season"]
            )
            episode = (
                row["episode"] if row["episode"] is not None else row["native_episode"]
            )
            label += f".S{season:02d}E{episode:02d}"
        label += "." + LANGUAGES[row["language"]].replace(" ", ".")
        if row.get("height") is not None:
            label += f".{row['height']}p"
            if row.get("estimated"):
                label += ".Estimated"
            elif row.get("codec"):
                label += "." + row["codec"].upper()
        if row["mode"] == "strm":
            label += ".STRM"
        link = magnet.encode(payload, label)
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = label
        ET.SubElement(
            item, "guid", {"isPermaLink": "false"}
        ).text = f"urn:anibridge:release:1:{row['release_id']}:{row['mode']}"
        ET.SubElement(item, "pubDate").text = formatdate(
            row["first_seen_at"], usegmt=True
        )
        ET.SubElement(item, "link").text = link
        ET.SubElement(
            item,
            "enclosure",
            {"url": link, "length": "0", "type": "application/x-bittorrent"},
        )
        attributes = {
            "magneturl": link,
            "infohash": identity.infohash(row["release_id"], row["mode"]),
            "size": "0",
            "category": str(row["category"]),
            "seeders": "1",
            "peers": "1",
        }
        if canonical:
            attributes[
                {
                    "tvdb": "tvdbid",
                    "tmdb-tv": "tmdbid",
                    "tmdb-movie": "tmdbid",
                    "imdb": "imdbid",
                }[canonical["namespace"]]
            ] = canonical["external_id"]
            if row["kind"] == "episode":
                attributes.update(
                    season=str(canonical["season"]), episode=str(canonical["episode"])
                )
        for name, value in attributes.items():
            ET.SubElement(item, "torznab:attr", {"name": name, "value": value})
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)
