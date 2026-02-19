#!/bin/bash
# OhVali AI News - Auto Deploy Script
# Scrape news + push automatiquement (news only)
# Robuste: timeout 5 min, retry, gestion d'erreurs

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NEWS_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$SCRIPT_DIR/last_run.log"

# Mistral API for translations and hot news scoring
export MISTRAL_API_KEY="$(cat /home/ubuntu/.openclaw/workspace/.secrets/mistral.key)"

TOKEN_FILE="/home/ubuntu/.openclaw/workspace/.secrets/github_valerium_news.token"

echo "=== OhVali News Auto-Deploy ===" | tee "$LOG_FILE"
echo "$(date)" | tee -a "$LOG_FILE"

# Run scraper with timeout (5 minutes max)
echo "Running scraper (timeout 300s)..." | tee -a "$LOG_FILE"
cd "$SCRIPT_DIR"
source venv/bin/activate

# Run with timeout, unbuffered output
if timeout 300 python -u news_scraper.py 2>&1 | tee -a "$LOG_FILE"; then
    echo "Scraper completed successfully" | tee -a "$LOG_FILE"
else
    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 124 ]; then
        echo "ERROR: Scraper timed out after 5 minutes" | tee -a "$LOG_FILE"
    else
        echo "ERROR: Scraper failed with exit code $EXIT_CODE" | tee -a "$LOG_FILE"
    fi
    # Don't exit - still try to push whatever we have
fi

# Check if news.json was updated
if [ -f "$NEWS_DIR/news.json" ]; then
    # Git push (news.json only)
    echo "Pushing news.json to GitHub..." | tee -a "$LOG_FILE"
    cd "$NEWS_DIR"
    git add news.json
    
    if git diff --cached --quiet; then
        echo "No changes to commit" | tee -a "$LOG_FILE"
    else
        git commit -m "Auto-update news $(date '+%Y-%m-%d %H:%M')" | tee -a "$LOG_FILE"
        git remote set-url origin "https://$(cat $TOKEN_FILE)@github.com/crapucorp/valerium-ai-news.git"
        if git push 2>&1 | tee -a "$LOG_FILE"; then
            echo "Push successful" | tee -a "$LOG_FILE"
        else
            echo "Push failed" | tee -a "$LOG_FILE"
        fi
    fi
else
    echo "ERROR: news.json not found" | tee -a "$LOG_FILE"
fi

echo "=== Done $(date) ===" | tee -a "$LOG_FILE"
