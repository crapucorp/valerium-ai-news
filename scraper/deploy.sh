#!/bin/bash
# OhVali AI News - Auto Deploy Script
# Run scraper and push to GitHub

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NEWS_DIR="$(dirname "$SCRIPT_DIR")"
REPO_DIR="/home/ubuntu/.openclaw/workspace/valerium-ai-news"
TOKEN_FILE="/home/ubuntu/.openclaw/workspace/.secrets/github_valerium_news.token"

# Mistral API for translations
export MISTRAL_API_KEY="REDACTED_MISTRAL_KEY"

echo "=== OhVali News Auto-Deploy ==="
echo "$(date)"

# Run scraper
echo "Running scraper..."
cd "$SCRIPT_DIR"
source venv/bin/activate
python news_scraper.py

# Copy updated files to repo
echo "Copying to repo..."
cp "$NEWS_DIR/news.json" "$REPO_DIR/"

# Git push
echo "Pushing to GitHub..."
cd "$REPO_DIR"
git add news.json
git commit -m "Auto-update news $(date '+%Y-%m-%d %H:%M')" || echo "No changes to commit"
git remote set-url origin "https://$(cat $TOKEN_FILE)@github.com/crapucorp/valerium-ai-news.git"
git push || echo "Nothing to push"

echo "=== Done ==="
