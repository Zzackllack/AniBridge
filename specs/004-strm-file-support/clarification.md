# Clarification Questions (STRM Support)

Answer any way you like; the `a/b/c` options are just to make it quick.

## 1) What URL should the `.strm` contain?

a) The resolved provider “direct URL” (may expire; simplest)  -> Current implementation 
b) A stable AniBridge URL (e.g., `https://anibridge.example/stream/...`) that proxies/refreshes underlying links  
c) A URL to a remote file host you control (template-based; e.g., S3/WebDAV/NFS gateway)

## 2) Where should the `.strm` file end up for your workflow to work?

a) In `DOWNLOAD_DIR` (whatever the “download client output” is) and let Sonarr import it  
b) Directly in the final Jellyfin library path (bypassing Sonarr import logic)  
c) Both (write to download dir and also copy/link into a library path)

## 3) How should STRM variants be named in Torznab and on disk?

a) Suffix `[STRM]` -> Current implementation
b) Prefix `[STRM]` (more visible in some UIs)
c) A different, configurable tag (env var), e.g. `.STRM` or `[REMOTE]`

## 4) How should Sonarr “quality” sorting behave for STRM variants?

a) Prefer normal downloads by default (STRM is an explicit opt-in choice)  
b) Prefer STRM when available (make STRM “win” sorting/selection)  
c) Make it configurable (e.g., STRM uses same size/quality tags vs tiny size)

## 5) What should happen if the STRM URL is expired/unplayable later?

a) Do nothing; user regenerates/researches manually  
b) Add an endpoint/CLI to “refresh” `.strm` files by re-resolving provider URLs  
c) Serve a stable AniBridge proxy URL so expiry is handled internally
