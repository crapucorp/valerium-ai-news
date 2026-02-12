#!/usr/bin/env python3
"""
Regenerate and clean all article summaries in news.json.
Removes prompt leaks and ensures all articles have FR translations.
"""

import os
import json
import re
import requests
from pathlib import Path
from datetime import datetime

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

def clean_prompt_leaks(text):
    """Remove any leaked prompt instructions from text."""
    if not text:
        return text
    
    # Patterns to remove
    patterns = [
        r'\[Contexte:.*?\]',
        r'\[Context:.*?\]',
        r'\[Conclusion:.*?\]',
        r'\[Fait important \d+\]',
        r'\[Key fact \d+\]',
        r'\[.*?phrases qui expliquent.*?\]',
        r'\[.*?sentences explaining.*?\]',
        r'\[.*?implications.*?\]',
        r'\[.*?what this changes.*?\]',
        r'^\s*\[.*?\]\s*$',  # Lines that are just [...]
        r'\n\[.*?\]\n',  # Lines starting with [...]
    ]
    
    cleaned = text
    for pattern in patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
    
    # Clean up multiple newlines
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    cleaned = cleaned.strip()
    
    return cleaned

def needs_translation(article):
    """Check if article needs FR translation."""
    title = article.get("title", "")
    title_en = article.get("title_en", "")
    
    # If title == title_en, it's probably not translated
    if title == title_en and title:
        return True
    
    return False

def has_prompt_leaks(article):
    """Check if article has visible prompt instructions."""
    fields = ["long_summary", "long_summary_en", "summary", "summary_en"]
    patterns = [r'\[Contexte:', r'\[Context:', r'\[Conclusion:', r'\[Fait important', r'\[Key fact']
    
    for field in fields:
        text = article.get(field, "")
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
    return False

def regenerate_summary(article):
    """Regenerate article summaries using Claude Sonnet 4.5."""
    if not ANTHROPIC_API_KEY:
        print("  No API key - cleaning only")
        return clean_article(article)
    
    title_en = article.get("title_en") or article.get("title", "")
    content = article.get("summary_en") or article.get("summary", "")
    
    prompt = f"""Tu es un journaliste tech expert. Traduis et améliore cet article.

TITRE: {title_en}
RÉSUMÉ: {content}

Génère un JSON avec:
{{
  "title": "Titre traduit en français (accrocheur)",
  "title_en": "{title_en}",
  "summary": "Résumé FR percutant (max 150 caractères)",
  "summary_en": "EN summary (max 150 chars)",
  "long_summary": "Contexte en 1-2 phrases.\\n\\nPoints clés :\\n• Premier point\\n• Deuxième point\\n• Troisième point\\n\\nConclusion.",
  "long_summary_en": "Context in 1-2 sentences.\\n\\nKey points:\\n• First point\\n• Second point\\n• Third point\\n\\nConclusion."
}}

IMPORTANT: Pas de texte entre crochets comme [Contexte:] - écris directement le contenu."""

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"
            },
            json={
                "model": "claude-sonnet-4-5-20250514",
                "max_tokens": 1500,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=60
        )
        if resp.status_code == 200:
            result = resp.json()["content"][0]["text"].strip()
            result = re.sub(r'^```json\s*', '', result)
            result = re.sub(r'\s*```$', '', result)
            parsed = json.loads(result)
            
            # Update article with cleaned content
            article["title"] = clean_prompt_leaks(parsed.get("title", article.get("title", "")))
            article["title_en"] = clean_prompt_leaks(parsed.get("title_en", article.get("title_en", "")))
            article["summary"] = clean_prompt_leaks(parsed.get("summary", article.get("summary", "")))
            article["summary_en"] = clean_prompt_leaks(parsed.get("summary_en", article.get("summary_en", "")))
            article["long_summary"] = clean_prompt_leaks(parsed.get("long_summary", article.get("long_summary", "")))
            article["long_summary_en"] = clean_prompt_leaks(parsed.get("long_summary_en", article.get("long_summary_en", "")))
            
            return article
        else:
            print(f"  API error: {resp.status_code}")
    except Exception as e:
        print(f"  Regeneration error: {e}")
    
    return clean_article(article)

def clean_article(article):
    """Just clean prompt leaks without regenerating."""
    for field in ["title", "title_en", "summary", "summary_en", "long_summary", "long_summary_en"]:
        if field in article:
            article[field] = clean_prompt_leaks(article[field])
    return article

def main():
    news_path = Path(__file__).parent.parent / "news.json"
    
    print("Loading news.json...")
    with open(news_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    categories = data.get("categories", {})
    total = sum(len(articles) for articles in categories.values())
    
    print(f"Processing {total} articles...\n")
    
    count = 0
    for cat, articles in categories.items():
        print(f"\n=== {cat.upper()} ({len(articles)} articles) ===")
        for i, article in enumerate(articles):
            count += 1
            title = article.get("title", "")[:50]
            
            needs_regen = needs_translation(article) or has_prompt_leaks(article)
            
            if needs_regen:
                print(f"[{count}/{total}] {title}... REGENERATING")
                articles[i] = regenerate_summary(article)
            else:
                print(f"[{count}/{total}] {title}... OK (cleaning)")
                articles[i] = clean_article(article)
    
    # Update timestamp
    data["lastUpdate"] = datetime.now().strftime("%d %B %Y - %H:%M")
    
    print(f"\nSaving to {news_path}...")
    with open(news_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print("Done!")

if __name__ == "__main__":
    main()
