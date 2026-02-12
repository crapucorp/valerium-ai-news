#!/bin/bash
# OhVali AI News - Auto Deploy Script
# Scrape news + push automatiquement (news only)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NEWS_DIR="$(dirname "$SCRIPT_DIR")"

# Anthropic API for translations (Claude Sonnet 4.5)
export ANTHROPIC_API_KEY="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"

TOKEN_FILE="/home/ubuntu/.openclaw/workspace/.secrets/github_valerium_news.token"

echo "=== OhVali News Auto-Deploy ==="
echo "$(date)"

# Run scraper
echo "Running scraper..."
cd "$SCRIPT_DIR"
source venv/bin/activate
python news_scraper.py

# Git push (news.json only)
echo "Pushing news.json to GitHub..."
cd "$NEWS_DIR"
git add news.json
git commit -m "Auto-update news $(date '+%Y-%m-%d %H:%M')" || echo "No changes to commit"
git remote set-url origin "https://$(cat $TOKEN_FILE)@github.com/crapucorp/valerium-ai-news.git"
git push || echo "Nothing to push"

echo "=== Done ==="
