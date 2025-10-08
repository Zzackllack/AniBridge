# Quickstart — Absolute Numbering Support Feature

1. **Check out feature branch**  
   ```bash
   git checkout 001-absolute-episode-numbers
   ```

2. **Install dependencies** (Python 3.12 environment assumed)  
   ```bash
   pip install -r requirements-dev.txt
   ```

3. **Run baseline tests** to confirm clean slate  
   ```bash
   pytest
   ```

4. **Export environment toggle (optional fallback)**  
   ```bash
   export ANIBRIDGE_FALLBACK_ALL_EPISODES=false  # enable later if you need catalogue fallback
   ```

5. **Start AniBridge locally**  
   ```bash
   python -m app.main
   ```

6. **Trigger an absolute-number search** via Torznab  
   ```bash
   curl "http://localhost:8000/torznab/api?t=search&series=naruto&sonarrAbsolute=true&q=003"
   ```
   Verify the response returns the mapped SxxEyy episode and includes helper metadata.

7. **Validate qBittorrent shim output**  
   ```bash
   curl "http://localhost:8000/api/v2/sync/maindata" | jq '.torrents'
   ```
   Ensure absolute-numbered jobs expose `anibridgeAbsolute` and consistent naming.

8. **Run feature tests** after implementation  
   ```bash
   pytest tests/api/test_torznab_absolute.py tests/api/test_qbittorrent_absolute.py
   ```

9. **Update documentation**  
   ```bash
   pnpm --prefix docs install
   pnpm --prefix docs run build
   ```
   Preview changes locally and confirm new sections describing absolute numbering support.
