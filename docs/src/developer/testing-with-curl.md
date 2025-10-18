# Testing AniBridge with curl (developer guide)

This short guide shows how to emulate Sonarr's behavior using curl: perform a Torznab tvsearch for an episode, extract the magnet (or enclosure URL) from the Torznab XML, add the magnet to the qBittorrent shim, and verify the download/job status.

Use these examples from macOS/zsh. Adjust HOST, port, and API key values for your environment.

## Quick environment variables

```zsh
HOST="http://localhost:8000"
CATEGORY="tv-sonarr"
TORZNAB_INDEX="$HOST/torznab/api"
QBIT="$HOST/api/v2"
```

## 1) Check Torznab caps (optional)

```zsh
curl -s "$TORZNAB_INDEX?t=caps" | xmllint --format - 2>/dev/null | sed -n '1,40p'
```

Fallback (no xmllint):

```zsh
curl -s "$TORZNAB_INDEX?t=caps" | sed -n '1,20p'
```

## 2) Perform a tvsearch (episode search)

Replace values below with the show title, season, and episode you want to test:

```zsh
TITLE="Seishun Buta Yarou wa Bunny Girl Senpai no Yume wo Minai"
SEASON=1
EPISODE=4

curl -s --get "$TORZNAB_INDEX" \
  --data-urlencode "t=tvsearch" \
  --data-urlencode "q=$TITLE" \
  --data-urlencode "season=$SEASON" \
  --data-urlencode "ep=$EPISODE" \
  --data-urlencode "cat=5070" \
  -H "Accept: application/xml" \
  -o /tmp/torznab_search.xml

# Inspect
xmllint --format /tmp/torznab_search.xml | sed -n '1,120p'
```

If xmllint is not available:

```zsh
sed -n '1,120p' /tmp/torznab_search.xml
```

## 3) Extract the magnet/enclosure URL

Preferred approach (xmllint + XPath):

```zsh
MAGNET=$(xmllint --xpath "string(//item/enclosure/@url)" /tmp/torznab_search.xml 2>/dev/null)

if [ -z "$MAGNET" ]; then
  MAGNET=$(xmllint --xpath "string(//item/link[contains(.,'magnet:')])" /tmp/torznab_search.xml 2>/dev/null)
fi
if [ -z "$MAGNET" ]; then
  MAGNET=$(xmllint --xpath "string(//item/description[contains(.,'magnet:')])" /tmp/torznab_search.xml 2>/dev/null | grep -o 'magnet:[^\"< ]*' | head -n1)
fi
```

Fallback with grep/sed:

```zsh
MAGNET=$(grep -o 'magnet:[^\"< ]*' /tmp/torznab_search.xml | head -n1)
```

Show what we found:

```zsh
echo "Magnet: $MAGNET"
```

If empty, inspect `/tmp/torznab_search.xml` to find the node that contains the provider URL or magnet.

## 4) (Optional) Login to qBittorrent shim to get cookie

Some qBittorrent-like shims set a SID cookie. AniBridge typically accepts empty login (or none). To get a cookie file:

```zsh
curl -i -s -c /tmp/qb_cookies.txt -X POST "$HOST/api/v2/auth/login" -d "username=&password=&remember=false"
cat /tmp/qb_cookies.txt
```

If your instance does not require login, skip this step.

## 5) Add the magnet to the qBittorrent shim (trigger download)

```zsh
if [ -z "$MAGNET" ]; then
  echo "No magnet found; aborting add."
  exit 1
fi

curl -s -b /tmp/qb_cookies.txt -X POST "$QBIT/torrents/add" \
  -F "urls=$MAGNET" \
  -F "category=$CATEGORY" \
  -F "skip_checking=true" \
  -F "paused=false" \
  -F "root_folder=false" \
  -o /tmp/qbit_add_response.txt

cat /tmp/qbit_add_response.txt
```

Notes:

- AniBridge's shim may return plain text `Ok.` on success. A 200 response generally means the torrent was accepted.

- If the add endpoint expects different form fields, inspect `app/api/qbittorrent/torrents.py`.

## 6) Verify the torrent/job appears

List torrents for the category:

```zsh
curl -s -G "$QBIT/torrents/info" --data-urlencode "category=$CATEGORY" | jq .
```

Check `sync/maindata` (used by Sonarr):

```zsh
curl -s -G "$QBIT/sync/maindata" | jq '.'
```

If you don't have `jq`:

```zsh
curl -s -G "$QBIT/torrents/info?category=$CATEGORY" | sed -n '1,120p'
```

## 7) Alternative: Use legacy downloader endpoint

AniBridge includes a legacy endpoint that can start a download by slug/season/episode. Example (replace slug):

```zsh
curl -s "$HOST/downloader/download" \
  -G --data-urlencode "slug=seishun-buta-yarou-wa-bunny-girl-senpai-no-yume-wo-minai" \
  --data-urlencode "season=1" \
  --data-urlencode "episode=4" \
  -o /tmp/legacy_download_response.txt

sed -n '1,120p' /tmp/legacy_download_response.txt
```

## 8) Follow logs while the download runs

If logs are written to `data/terminal-YYYY-MM-DD.log`:

```zsh
tail -f data/terminal-$(date +%F)_*.log
```

In Docker:

```zsh
docker compose logs -f anibridge
```

## Helpful tips and edge cases

- If Torznab returns provider page URLs instead of magnet URIs, you may need to use the legacy downloader or inspect the `guid`/`link` to map to the internal job creation endpoint.
- If the Torznab endpoint requires `apikey`, add `&apikey=YOUR_KEY` to the tvsearch request.
- If the qBittorrent shim returns errors, inspect `app/api/qbittorrent/torrents.py` to verify required parameters.
