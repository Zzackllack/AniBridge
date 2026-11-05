"""User-local RSS formatting over shared metadata contracts."""

import xml.etree.ElementTree as ET
from email.utils import formatdate
from catalog_core import identity, magnet
from catalog_core.query import LANGUAGES, TORZNAB, NEWZNAB
from catalog_core.query import parse as parse

_AUDIO_LANGUAGE_NAMES = {
    "deu": "German",
    "eng": "English",
    "jpn": "Japanese",
    "ita": "Italian",
    "spa": "Spanish",
    "fra": "French",
    "kor": "Korean",
    "rus": "Russian",
    "tur": "Turkish",
    "ara": "Arabic",
    "por": "Portuguese",
    "zho": "Chinese",
    "hin": "Hindi",
    "pol": "Polish",
    "nld": "Dutch",
    "und": "Undetermined",
}


def rss(
    rows: list[dict], total: int, offset: int, *, seeders: int, leechers: int
) -> bytes:
    # Match the legacy formatter: compatibility counts cannot be negative.
    seeders, leechers = max(0, seeders), max(0, leechers)
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
        metadata = row.get("release_metadata")
        if row["provider"] == "filmo.to":
            if metadata is None or row.get("variant_anchor") is None:
                raise ValueError("filmo_variant_metadata_required")
            payload["variant_anchor"] = row["variant_anchor"]
            payload["release_metadata"] = metadata
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
        if metadata is None:
            label += "." + LANGUAGES[row["language"]].replace(" ", ".")
        else:
            for language in metadata["audio_languages"]:
                label += "." + _AUDIO_LANGUAGE_NAMES.get(language, language).replace(
                    " ", "."
                )
            quality = metadata["quality"]
            # Raw conflicting labels are evidence, not a safe client quality.
            if quality["source"] != "unknown":
                label += (
                    "."
                    + {
                        "bluray": "BluRay",
                        "web": "WEB",
                        "webdl": "WEB-DL",
                        "webrip": "WEBRip",
                        "cam": "CAM",
                        "telesync": "TS",
                        "telecine": "TC",
                        "dvd": "DVD",
                        "tv": "HDTV",
                    }[quality["source"]]
                )
            if quality["resolution"] is not None:
                label += f".{quality['resolution']}p"
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
        if metadata is not None:
            audio = ", ".join(
                _AUDIO_LANGUAGE_NAMES.get(language, language)
                for language in metadata["audio_languages"]
            )
            subtitles = metadata["subtitle_languages"]
            subtitle_text = (
                "unknown"
                if subtitles is None
                else ", ".join(
                    _AUDIO_LANGUAGE_NAMES.get(language, language)
                    for language in subtitles
                )
                or "none declared"
            )
            ET.SubElement(item, "description").text = (
                f"Filmo audio: {audio}; subtitles: {subtitle_text}; "
                f"provider label: {metadata['language_label']}; "
                f"declared quality labels: {', '.join(metadata['quality']['labels']) or 'unknown'}"
            )
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
            "seeders": str(seeders),
            "leechers": str(leechers),
            "peers": str(seeders + leechers),
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
        if metadata is not None:
            attributes.update(
                anibridge_host=metadata["host"],
                anibridge_source_id=metadata["native_id"],
                anibridge_audio_languages=",".join(metadata["audio_languages"]),
                anibridge_audio_role=metadata["audio_role"],
                anibridge_subtitle_mode=metadata["subtitle_mode"],
            )
            if metadata["subtitle_languages"] is not None:
                attributes["anibridge_subtitle_languages"] = ",".join(
                    metadata["subtitle_languages"]
                )
            quality = metadata["quality"]
            attributes["anibridge_source_claim"] = quality["source"]
            if quality["resolution"] is not None:
                attributes["anibridge_resolution_claim"] = str(quality["resolution"])
            for language in metadata["audio_languages"]:
                if language != "und":
                    ET.SubElement(
                        item,
                        "torznab:attr",
                        {
                            "name": "language",
                            "value": _AUDIO_LANGUAGE_NAMES.get(language, language),
                        },
                    )
        for name, value in attributes.items():
            ET.SubElement(item, "torznab:attr", {"name": name, "value": value})
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)
