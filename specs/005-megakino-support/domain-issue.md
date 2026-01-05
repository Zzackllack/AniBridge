# Megakino Domain Issue

**Build dynamic domain resolution infrastructure for megakino that somehow fetches the current domain on startup. You'll need to research and think through the best approach to do this. I would prefer an approach that does not rely on hosting anything publicly, everything should happen locally or within the app.**

**This is how the https://github.com/Yezun-hikari/new-domain-check repository handles megakino domain rotation. We can adapt this approach to avoid hardcoding the megakino domain in AniBridge... Do NOT fetch the domain.txt file from this repo at runtime, instead implement it directly in AniBridge.**

File: *.github/workflows/check-megakino-domain.yml*

```yaml
name: Check All Domains

on:
  schedule:
    - cron: '0 */6* **'  # Run every 6 hours
  workflow_dispatch:      # Allow manual runs

permissions:
  contents: write

jobs:
  check-domains:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Check Domains for Redirects
        id: check
        run: |
          CHANGES_DETECTED=false
          UPDATED_DOMAINS=""

          for monitor_dir in monitors/*; do
            if [ -d "$monitor_dir" ]; then
              MONITOR_NAME=$(basename "$monitor_dir")
              DOMAIN_FILE="$monitor_dir/domain.txt"
              HISTORY_FILE="$monitor_dir/history.txt"

              if [ -f "$DOMAIN_FILE" ]; then
                CURRENT_DOMAIN=$(cat "$DOMAIN_FILE" | tr -d '\n\r')
                echo "🔎 Checking monitor: $MONITOR_NAME (Domain: $CURRENT_DOMAIN)"

                # Add https:// if not present
                if [[ ! "$CURRENT_DOMAIN" =~ ^https?:// ]]; then
                  CURRENT_DOMAIN_URL="https://$CURRENT_DOMAIN"
                else
                  CURRENT_DOMAIN_URL="$CURRENT_DOMAIN"
                fi

                # Follow redirects to get the final URL
                FINAL_URL=$(curl -sLI -o /dev/null -w '%{url_effective}' "$CURRENT_DOMAIN_URL")

                # Clean URLs for comparison (remove protocol and trailing slashes)
                CURRENT_DOMAIN_CLEAN=$(echo "$CURRENT_DOMAIN_URL" | sed -e 's|^https\?://||' -e 's:/*$::')
                FINAL_DOMAIN_CLEAN=$(echo "$FINAL_URL" | sed -e 's|^https\?://||' -e 's:/*$::')

                if [ "$FINAL_DOMAIN_CLEAN" != "$CURRENT_DOMAIN_CLEAN" ] && [ -n "$FINAL_DOMAIN_CLEAN" ]; then
                  echo "  🔄 Redirect detected: $CURRENT_DOMAIN_CLEAN → $FINAL_DOMAIN_CLEAN"
                  CHANGES_DETECTED=true

                  # Add to list of updated domains for the commit message
                  if [ -n "$UPDATED_DOMAINS" ]; then
                    UPDATED_DOMAINS+=", "
                  fi
                  UPDATED_DOMAINS+="$MONITOR_NAME"

                  # 1. Update domain.txt
                  echo "$FINAL_DOMAIN_CLEAN" > "$DOMAIN_FILE"

                  # 2. Append to history.txt
                  TIMESTAMP=$(date -u +'%Y-%m-%d %H:%M:%S UTC')
                  echo "$TIMESTAMP | $CURRENT_DOMAIN_CLEAN → $FINAL_DOMAIN_CLEAN" >> "$HISTORY_FILE"

                  echo "  📝 Files updated for $MONITOR_NAME."
                else
                  echo "  ✅ No change detected for $MONITOR_NAME."
                fi
              else
                echo "  ⚠️ No domain.txt found in $monitor_dir, skipping."
              fi
              echo "" # Newline for cleaner logs
            fi
          done

          # Set outputs for the next steps
          echo "changes_detected=$CHANGES_DETECTED" >> $GITHUB_OUTPUT
          echo "updated_domains=$UPDATED_DOMAINS" >> $GITHUB_OUTPUT

      - name: Commit and Push Changes
        if: steps.check.outputs.changes_detected == 'true'
        run: |
          git config --local user.email "github-actions[bot]@users.noreply.github.com"
          git config --local user.name "github-actions[bot]"
          git add monitors/
          COMMIT_MESSAGE="🔄 Domain(s) updated: ${{ steps.check.outputs.updated_domains }}"
          git commit -m "$COMMIT_MESSAGE"
          git push
```
