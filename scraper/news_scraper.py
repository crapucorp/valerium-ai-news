#!/usr/bin/env python3
"""
OhVali AI News - Auto Scraper
Scrape AI news, translate to FR, merge with existing articles.
"""

import os
import json
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import feedparser
from pathlib import Path

# Configuration
SOURCES = {
    "techcrunch_ai": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "theverge_ai": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "wired_ai": "https://www.wired.com/feed/tag/ai/latest/rss",
    "ars_ai": "https://feeds.arstechnica.com/arstechnica/technology-lab",
    "reuters_tech": "https://www.reutersagency.com/feed/?best-topics=tech",
}

CATEGORIES_KEYWORDS = {
    "video": ["video", "sora", "runway", "pika", "kling", "seedance", "gen-3", "gen-4", "veo", "hailuo", "luma"],
    "image": ["image", "dall-e", "midjourney", "stable diffusion", "flux", "ideogram", "imagen", "photo"],
    "llm": ["gpt", "claude", "gemini", "llama", "mistral", "llm", "chatbot", "language model", "anthropic", "openai", "chatgpt"],
    "audio": ["audio", "music", "suno", "udio", "elevenlabs", "voice", "tts", "speech", "sound"],
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# Anthropic API for translation (Claude Sonnet 4.5)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

def clean_prompt_leaks(text):
    """Remove any leaked prompt instructions from text."""
    if not text:
        return text
    
    # Patterns to remove (prompt instructions that leaked)
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
        r'^\[.*?\]\s*\n',  # Lines starting with [...]
    ]
    
    cleaned = text
    for pattern in patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
    
    # Clean up multiple newlines
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    cleaned = cleaned.strip()
    
    return cleaned

def generate_article_summary(title, content, url):
    """Generate professional FR/EN summaries using Claude Sonnet 4.5."""
    if not ANTHROPIC_API_KEY:
        return {
            "title": title,
            "title_en": title,
            "summary": content[:200],
            "summary_en": content[:200],
            "long_summary": content,
            "long_summary_en": content
        }
    
    prompt = f"""Tu es un journaliste tech expert. Génère un article structuré en FR et EN.

TITRE ORIGINAL: {title}
CONTENU: {content}

FORMAT DE RÉPONSE - JSON strict:
{{
  "title": "Titre accrocheur traduit en français",
  "title_en": "Original or improved English title",
  "summary": "Résumé FR percutant en 1-2 phrases (max 150 caractères)",
  "summary_en": "Punchy EN summary in 1-2 sentences (max 150 chars)",
  "long_summary": "Contexte en 1-2 phrases.\\n\\nPoints clés :\\n• Premier point important\\n• Deuxième point\\n• Troisième point\\n\\nConclusion sur les implications.",
  "long_summary_en": "Context in 1-2 sentences.\\n\\nKey points:\\n• First key point\\n• Second point\\n• Third point\\n\\nConclusion on implications."
}}

RÈGLES STRICTES:
- NE PAS inclure de texte entre crochets comme [Contexte:] ou [Conclusion:]
- Écrire directement le contenu, pas des instructions
- Utiliser • pour les bullet points
- JSON valide uniquement, pas de markdown"""

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
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            },
            timeout=60
        )
        if resp.status_code == 200:
            result = resp.json()["content"][0]["text"].strip()
            # Remove markdown code blocks if present
            result = re.sub(r'^```json\s*', '', result)
            result = re.sub(r'\s*```$', '', result)
            parsed = json.loads(result)
            
            # Clean any leaked prompts from all fields
            return {
                "title": clean_prompt_leaks(parsed.get("title", title)),
                "title_en": clean_prompt_leaks(parsed.get("title_en", title)),
                "summary": clean_prompt_leaks(parsed.get("summary", content[:200])),
                "summary_en": clean_prompt_leaks(parsed.get("summary_en", content[:200])),
                "long_summary": clean_prompt_leaks(parsed.get("long_summary", content)),
                "long_summary_en": clean_prompt_leaks(parsed.get("long_summary_en", content))
            }
        else:
            print(f"  API error: {resp.status_code} - {resp.text[:100]}")
    except Exception as e:
        print(f"Summary generation error: {e}")
    
    # Fallback
    return {
        "title": title,
        "title_en": title,
        "summary": content[:200],
        "summary_en": content[:200],
        "long_summary": content,
        "long_summary_en": content
    }

def fetch_og_image(url):
    """Extract og:image from article URL."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        og_img = soup.find('meta', property='og:image')
        if og_img and og_img.get('content'):
            return og_img['content']
        
        tw_img = soup.find('meta', attrs={'name': 'twitter:image'})
        if tw_img and tw_img.get('content'):
            return tw_img['content']
        
        return None
    except Exception as e:
        print(f"Error fetching og:image from {url}: {e}")
        return None

def categorize_article(title, summary):
    """Categorize article based on keywords."""
    text = (title + " " + summary).lower()
    
    for category, keywords in CATEGORIES_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                return category
    
    return "general"

def fetch_rss_feed(feed_url, source_name):
    """Fetch and parse RSS feed."""
    try:
        feed = feedparser.parse(feed_url)
        articles = []
        
        for entry in feed.entries[:5]:  # Last 5 articles per source
            pub_date = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                pub_date = datetime(*entry.published_parsed[:6])
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                pub_date = datetime(*entry.updated_parsed[:6])
            
            # Skip articles older than 7 days
            if pub_date and (datetime.now() - pub_date).days > 7:
                continue
            
            title_en = entry.get('title', '')
            summary_en = BeautifulSoup(entry.get('summary', ''), 'html.parser').get_text()[:600]
            url = entry.get('link', '')
            
            # Generate French summary
            print(f"  Processing: {title_en[:50]}...")
            fr_content = generate_article_summary(title_en, summary_en, url)
            
            article = {
                "title": fr_content.get("title", title_en),
                "title_en": title_en,
                "summary": fr_content.get("summary", summary_en[:200]),
                "summary_en": summary_en[:200],
                "long_summary": fr_content.get("long_summary", summary_en),
                "long_summary_en": summary_en,
                "url": url,
                "source": source_name,
                "date": pub_date.strftime("%d %B %Y") if pub_date else datetime.now().strftime("%d %B %Y"),
                "pub_date": pub_date.isoformat() if pub_date else None
            }
            
            # Get og:image
            article["image"] = fetch_og_image(article["url"]) or ""
            
            # Categorize
            article["category"] = categorize_article(title_en, summary_en)
            
            articles.append(article)
        
        return articles
    except Exception as e:
        print(f"Error fetching feed {feed_url}: {e}")
        return []

def score_hot_news(articles):
    """Use Claude to score articles by viral/mass appeal potential. Returns top 3."""
    if not ANTHROPIC_API_KEY or not articles:
        return []
    
    # Prepare article summaries for scoring
    article_list = []
    for i, a in enumerate(articles[:20]):  # Score max 20 recent articles
        article_list.append(f"{i+1}. {a.get('title_en', a.get('title', ''))} - {a.get('summary_en', a.get('summary', ''))[:100]}")
    
    articles_text = "\n".join(article_list)
    
    prompt = f"""Tu es un expert en viralité des news tech/IA. Analyse ces articles et identifie les 3 qui ont le plus de potentiel viral pour le grand public (pas les niches techniques).

Critères de viralité:
- Impact sur la vie quotidienne des gens
- Sujet controversé ou surprenant
- Grosses entreprises connues (OpenAI, Google, Meta, etc.)
- Argent/levées de fonds impressionnantes
- Avancées spectaculaires visibles

ARTICLES:
{articles_text}

Réponds UNIQUEMENT avec les numéros des 3 articles les plus viraux, séparés par des virgules.
Exemple: 2, 5, 8"""

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
                "max_tokens": 100,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        if resp.status_code == 200:
            result = resp.json()["content"][0]["text"].strip()
            # Parse numbers from response
            numbers = [int(n.strip()) for n in re.findall(r'\d+', result)][:3]
            hot_articles = []
            for n in numbers:
                if 1 <= n <= len(articles):
                    hot_articles.append(articles[n-1])
            print(f"  Hot news selected: {numbers}")
            return hot_articles
    except Exception as e:
        print(f"Hot news scoring error: {e}")
    
    # Fallback: return first 3 articles
    return articles[:3]

def load_existing_news(path):
    """Load existing news.json."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {"lastUpdate": "", "categories": {"general": [], "image": [], "video": [], "llm": [], "audio": []}, "hotNews": []}

def get_existing_urls(news_data):
    """Get all existing article URLs to avoid duplicates."""
    urls = set()
    for cat, articles in news_data.get("categories", {}).items():
        for article in articles:
            urls.add(article.get("url", ""))
    return urls

def scrape_all_sources():
    """Scrape all configured sources."""
    all_articles = []
    
    source_names = {
        "techcrunch_ai": "TechCrunch",
        "theverge_ai": "The Verge",
        "wired_ai": "Wired",
        "ars_ai": "Ars Technica",
        "reuters_tech": "Reuters",
    }
    
    for key, url in SOURCES.items():
        name = source_names.get(key, key)
        print(f"Scraping {name}...")
        articles = fetch_rss_feed(url, name)
        all_articles.extend(articles)
        print(f"  Found {len(articles)} articles")
    
    return all_articles

def merge_news(existing_data, new_articles):
    """Merge new articles into existing data without duplicates."""
    existing_urls = get_existing_urls(existing_data)
    
    categories = existing_data.get("categories", {
        "general": [], "image": [], "video": [], "llm": [], "audio": []
    })
    
    added = 0
    for article in new_articles:
        if article["url"] in existing_urls:
            continue
        
        cat = article.get("category", "general")
        if cat not in categories:
            cat = "general"
        
        news_item = {
            "title": article["title"],
            "title_en": article["title_en"],
            "summary": article["summary"],
            "summary_en": article["summary_en"],
            "long_summary": article.get("long_summary", article["summary"]),
            "long_summary_en": article.get("long_summary_en", article["summary_en"]),
            "image": article.get("image", ""),
            "source": article["source"],
            "url": article["url"],
            "date": article["date"]
        }
        
        # Add at the beginning (newest first)
        categories[cat].insert(0, news_item)
        added += 1
    
    # Limit each category to 15 articles
    for cat in categories:
        categories[cat] = categories[cat][:15]
    
    print(f"Added {added} new articles")
    
    # Collect all recent articles for hot news scoring
    all_recent = []
    for cat, items in categories.items():
        all_recent.extend(items[:5])  # Top 5 from each category
    
    # Score and select hot news
    print("Scoring hot news...")
    hot_news = score_hot_news(all_recent)
    
    # Format hot news for JSON
    hot_news_formatted = []
    for article in hot_news:
        hot_news_formatted.append({
            "title": article.get("title", ""),
            "title_en": article.get("title_en", ""),
            "source": article.get("source", ""),
            "url": article.get("url", ""),
            "date": article.get("date", "")
        })
    
    return {
        "lastUpdate": datetime.now().strftime("%d %B %Y - %H:%M"),
        "categories": categories,
        "hotNews": hot_news_formatted
    }

def save_news_json(news_data, output_path):
    """Save news.json file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(news_data, f, ensure_ascii=False, indent=2)
    print(f"Saved to {output_path}")

def main():
    """Main scraper function."""
    print("=" * 50)
    print("OhVali AI News Scraper")
    print("=" * 50)
    
    # Load existing articles
    news_path = Path(__file__).parent.parent / "news.json"
    existing_data = load_existing_news(news_path)
    print(f"Loaded existing news.json")
    
    # Scrape new articles
    new_articles = scrape_all_sources()
    print(f"\nTotal new articles found: {len(new_articles)}")
    
    # Merge
    merged_data = merge_news(existing_data, new_articles)
    
    # Save
    save_news_json(merged_data, news_path)
    
    # Stats
    print("\nCategories:")
    for cat, items in merged_data["categories"].items():
        print(f"  {cat}: {len(items)} articles")
    
    print("\nDone!")

if __name__ == "__main__":
    main()
