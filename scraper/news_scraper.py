#!/usr/bin/env python3
"""
OhVali AI News - Auto Scraper
Scrape AI news via Brave Search + RSS, translate to FR, merge with existing articles.
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
BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", "BSAi4x2_TyBxgRh3SX_PVd8rm64BjSV")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")  # Fallback when Brave rate limits
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")  # GPT fallback (OAuth token from OpenClaw)

RSS_SOURCES = {
    "techcrunch_ai": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "theverge_ai": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "wired_ai": "https://www.wired.com/feed/tag/ai/latest/rss",
    "ars_ai": "https://feeds.arstechnica.com/arstechnica/technology-lab",
    "reuters_tech": "https://www.reutersagency.com/feed/?best-topics=tech",
}

# Brave Search queries for AI news (focused, 3 queries max to avoid timeout)
BRAVE_QUERIES = [
    "AI artificial intelligence news today",
    "OpenAI Google Anthropic news",
    "AI video image generation news",
]

CATEGORIES_KEYWORDS = {
    "video": ["video", "sora", "runway", "pika", "kling", "seedance", "gen-3", "gen-4", "veo", "hailuo", "luma"],
    "image": ["image", "dall-e", "midjourney", "stable diffusion", "flux", "ideogram", "imagen", "photo"],
    "llm": ["gpt", "claude", "gemini", "llama", "mistral", "llm", "chatbot", "language model", "anthropic", "openai", "chatgpt"],
    "audio": ["audio", "music", "suno", "udio", "elevenlabs", "voice", "tts", "speech", "sound"],
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# Mistral API for translation
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "REDACTED_MISTRAL_KEY")

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
    """Generate professional FR/EN summaries using Mistral."""
    if not MISTRAL_API_KEY:
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
            "https://api.mistral.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {MISTRAL_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "mistral-small-latest",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1500
            },
            timeout=60
        )
        if resp.status_code == 200:
            result = resp.json()["choices"][0]["message"]["content"].strip()
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

def gpt_search_news():
    """Use OpenAI GPT API as fallback to find trending AI news when Brave rate limits."""
    if not OPENAI_API_KEY:
        print("  [GPT] No API key configured, skipping fallback")
        return []
    
    print("  [GPT] Using GPT as fallback for news search...")
    
    prompt = """Find the top 5 most important AI news stories from TODAY (February 13, 2026).
For each, provide:
- title: The headline
- url: The source URL  
- summary: 2 sentence summary
- source: The publication name

Focus on: OpenAI, Google Gemini, Anthropic Claude, GPT, Codex, major AI breakthroughs, AI safety news.

Return ONLY a JSON array, no other text:
[{"title": "...", "url": "...", "summary": "...", "source": "..."}]"""

    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1500,
                "temperature": 0.1
            },
            timeout=30
        )
        
        if resp.status_code == 200:
            result = resp.json()["choices"][0]["message"]["content"].strip()
            # Extract JSON from response
            result = re.sub(r'^```json\s*', '', result)
            result = re.sub(r'\s*```$', '', result)
            articles = json.loads(result)
            print(f"  [GPT] Found {len(articles)} articles")
            return articles
        else:
            print(f"  [GPT] Error {resp.status_code}: {resp.text[:100]}")
    except Exception as e:
        print(f"  [GPT] Search error: {e}")
    
    return []

def gemini_search_news():
    """Use Gemini API as fallback to find trending AI news when Brave rate limits."""
    if not GEMINI_API_KEY:
        # Try GPT instead
        return gpt_search_news()
    
    print("  [Gemini] Using Gemini as fallback for news search...")
    
    prompt = """Find the top 5 most important AI news stories from TODAY. 
For each, provide:
- title: The headline
- url: The source URL
- summary: 2 sentence summary
- source: The publication name

Focus on: OpenAI, Google Gemini, Anthropic Claude, GPT, major AI breakthroughs, AI safety news.

Return as JSON array:
[{"title": "...", "url": "...", "summary": "...", "source": "..."}]"""

    try:
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1}
            },
            timeout=30
        )
        
        if resp.status_code == 200:
            result = resp.json()
            text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            # Extract JSON from response
            text = re.sub(r'^```json\s*', '', text)
            text = re.sub(r'\s*```$', '', text)
            articles = json.loads(text)
            print(f"  [Gemini] Found {len(articles)} articles")
            return articles
        else:
            print(f"  [Gemini] Error {resp.status_code}: {resp.text[:100]}")
    except Exception as e:
        print(f"  [Gemini] Search error: {e}")
    
    # Try GPT as last resort
    return gpt_search_news()

def brave_search(query, count=10):
    """Search for AI news via Brave Search API."""
    if not BRAVE_API_KEY:
        print(f"  [Brave] No API key, skipping: {query}")
        return []
    
    try:
        resp = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": BRAVE_API_KEY
            },
            params={
                "q": query,
                "count": count,
                "freshness": "pd",  # Past day only
                "search_lang": "en"
            },
            timeout=15
        )
        
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("web", {}).get("results", [])
            return results
        else:
            print(f"  [Brave] Error {resp.status_code}: {resp.text[:100]}")
            return []
    except Exception as e:
        print(f"  [Brave] Search error: {e}")
        return []

def extract_article_content(url):
    """Extract main content from article URL."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Remove scripts, styles, nav, footer
        for tag in soup(['script', 'style', 'nav', 'footer', 'aside', 'header']):
            tag.decompose()
        
        # Try common article selectors
        article = soup.find('article') or soup.find(class_=re.compile(r'article|post|content|entry'))
        if article:
            text = article.get_text(separator=' ', strip=True)
        else:
            # Fallback to body
            text = soup.get_text(separator=' ', strip=True)
        
        # Clean up
        text = re.sub(r'\s+', ' ', text)
        return text[:2000]  # Limit for API
    except Exception as e:
        print(f"    Content extraction failed: {e}")
        return ""

def fetch_brave_articles(existing_urls):
    """Fetch articles from Brave Search across multiple queries."""
    articles = []
    seen_urls = set(existing_urls)
    
    import time
    for i, query in enumerate(BRAVE_QUERIES):
        if i > 0:
            time.sleep(3)  # Wait 3s between queries to avoid rate limit
        print(f"  [Brave] Searching: {query}")
        results = brave_search(query, count=5)
        
        for result in results:
            url = result.get("url", "")
            title = result.get("title", "")
            description = result.get("description", "")
            
            # Skip duplicates
            if url in seen_urls:
                continue
            seen_urls.add(url)
            
            # Skip non-news sites
            skip_domains = ['youtube.com', 'reddit.com', 'twitter.com', 'x.com', 'linkedin.com', 'facebook.com', 'wikipedia.org']
            if any(d in url.lower() for d in skip_domains):
                continue
            
            # Extract source name from URL
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.replace('www.', '')
            source = domain.split('.')[0].title()
            
            print(f"    Processing: {title[:50]}...")
            
            # Get full content for better summaries
            content = extract_article_content(url) or description
            
            # Generate summaries via Mistral
            fr_content = generate_article_summary(title, content[:1500], url)
            
            # Get og:image
            image = fetch_og_image(url) or ""
            
            article = {
                "title": fr_content.get("title", title),
                "title_en": title,
                "summary": fr_content.get("summary", description[:200]),
                "summary_en": description[:200],
                "long_summary": fr_content.get("long_summary", content[:600]),
                "long_summary_en": content[:600],
                "url": url,
                "source": source,
                "image": image,
                "date": datetime.now().strftime("%d %B %Y"),
                "category": categorize_article(title, description)
            }
            
            articles.append(article)
            
            # Limit total articles from Brave (10 max to avoid timeout)
            if len(articles) >= 10:
                return articles
    
    # FALLBACK: If Brave found few/no articles (rate limited), use Gemini
    if len(articles) < 3 and GEMINI_API_KEY:
        print(f"  [Brave] Only {len(articles)} articles found, trying Gemini fallback...")
        gemini_articles = gemini_search_news()
        
        for ga in gemini_articles:
            url = ga.get("url", "")
            if url in seen_urls:
                continue
            seen_urls.add(url)
            
            title = ga.get("title", "")
            summary = ga.get("summary", "")
            source = ga.get("source", "Unknown")
            
            print(f"    [Gemini] Processing: {title[:50]}...")
            
            # Generate FR summary
            fr_content = generate_article_summary(title, summary, url)
            image = fetch_og_image(url) or ""
            
            article = {
                "title": fr_content.get("title", title),
                "title_en": title,
                "summary": fr_content.get("summary", summary[:200]),
                "summary_en": summary[:200],
                "long_summary": fr_content.get("long_summary", summary),
                "long_summary_en": summary,
                "url": url,
                "source": source,
                "image": image,
                "date": datetime.now().strftime("%d %B %Y"),
                "category": categorize_article(title, summary)
            }
            articles.append(article)
    
    return articles

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
                "date": datetime.now().strftime("%d %B %Y"),  # Always use today's date for scraped articles
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

def get_trending_topics():
    """Scrape current AI trends from Brave Search."""
    print("  Fetching current AI trends...")
    trends = []
    
    try:
        # Search for viral/trending AI news
        resp = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": BRAVE_API_KEY
            },
            params={
                "q": "AI news trending viral today",
                "count": 10,
                "freshness": "pd",
                "search_lang": "en"
            },
            timeout=15
        )
        
        if resp.status_code == 200:
            results = resp.json().get("web", {}).get("results", [])
            for r in results:
                title = r.get("title", "").lower()
                desc = r.get("description", "").lower()
                text = title + " " + desc
                
                # Extract key topics/names
                keywords = ["gemini", "gpt", "openai", "anthropic", "claude", "deepseek", 
                           "meta", "llama", "mistral", "google", "microsoft", "apple",
                           "agi", "safety", "regulation", "hack", "attack", "viral",
                           "billion", "million", "breakthrough", "launch", "release"]
                
                for kw in keywords:
                    if kw in text and kw not in trends:
                        trends.append(kw)
            
            print(f"  Trends detected: {trends[:10]}")
    except Exception as e:
        print(f"  Trend detection error: {e}")
    
    return trends

def score_hot_news(articles):
    """Score articles based on HOT AI topics (Gemini, GPT, OpenAI, Anthropic). Returns top 3."""
    if not articles:
        return []
    
    # PRIORITY KEYWORDS - what's actually trending in AI right now
    priority_keywords = {
        "gemini": 20,      # Google's model - HUGE news right now
        "gpt": 15,         # OpenAI GPT
        "codex": 15,       # OpenAI Codex
        "openai": 12,      # OpenAI company
        "anthropic": 12,   # Anthropic/Claude
        "claude": 12,      # Claude model
        "deepseek": 10,    # DeepSeek trending
        "agi": 10,         # AGI discussions
    }
    
    # BREAKING NEWS indicators (specific events, not generic articles)
    breaking_keywords = {
        "100,000": 25,     # The 100k prompts story - SPECIFIC
        "100000": 25,
        "hack": 20,        # Security/hacking news
        "attack": 20,      # Attack news
        "attackers": 20,
        "prompted": 15,    # Prompt injection/attacks
        "clone": 15,       # Cloning attempts
        "quit": 15,        # Researcher quits
        "quits": 15,
        "exit": 15,        # Exits company
        "leaves": 12,
        "warns": 12,       # Warning = important
        "billion": 10,     # Funding news
        "million": 8,
        "launches": 8,
        "viral": 8,
        "safety": 8,
    }
    
    # Score each article (ALL of them)
    scored = []
    for i, article in enumerate(articles):  # Check ALL articles
        title = (article.get('title_en', '') + " " + article.get('title', '')).lower()
        summary = (article.get('summary_en', '') + " " + article.get('summary', '')).lower()
        long_summary = (article.get('long_summary_en', '') + " " + article.get('long_summary', '')).lower()
        text = title + " " + summary + " " + long_summary
        
        score = 0
        matched = []
        
        # Score priority keywords (company/model names)
        for keyword, points in priority_keywords.items():
            if keyword in text:
                # Title match = 2x points
                if keyword in title:
                    score += points * 2
                else:
                    score += points
                matched.append(keyword)
        
        # Score breaking news keywords (events/actions)
        breaking_matches = []
        for keyword, points in breaking_keywords.items():
            if keyword in text:
                if keyword in title:
                    score += points * 2
                else:
                    score += points
                breaking_matches.append(keyword)
        
        # BONUS: Articles with BOTH company name AND breaking event = real news
        if matched and breaking_matches:
            score += 20  # Big bonus for specific news about a company
            matched.extend(breaking_matches)
        
        scored.append((score, i, article, matched))
    
    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)
    
    # Get top 3
    hot_articles = []
    for score, idx, article, matched in scored[:3]:
        print(f"  Hot #{len(hot_articles)+1}: score={score}, keywords={matched}, title={article.get('title_en', '')[:60]}...")
        hot_articles.append(article)
    
    return hot_articles

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

def scrape_all_sources(existing_urls=None):
    """Scrape all configured sources: RSS feeds + Brave Search."""
    all_articles = []
    existing_urls = existing_urls or set()
    
    # 1. RSS feeds (reliable, structured)
    source_names = {
        "techcrunch_ai": "TechCrunch",
        "theverge_ai": "The Verge",
        "wired_ai": "Wired",
        "ars_ai": "Ars Technica",
        "reuters_tech": "Reuters",
    }
    
    print("\n--- RSS Feeds ---")
    for key, url in RSS_SOURCES.items():
        name = source_names.get(key, key)
        print(f"Scraping {name}...")
        articles = fetch_rss_feed(url, name)
        all_articles.extend(articles)
        print(f"  Found {len(articles)} articles")
    
    # 2. Brave Search (dynamic, wider coverage)
    print("\n--- Brave Search ---")
    brave_articles = fetch_brave_articles(existing_urls)
    all_articles.extend(brave_articles)
    print(f"  Total from Brave: {len(brave_articles)} articles")
    
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
    
    # Collect ALL articles for hot news scoring (not just top 5)
    all_recent = []
    for cat, items in categories.items():
        all_recent.extend(items)  # ALL articles from each category
    
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
    print("OhVali AI News Scraper v2 (RSS + Brave)")
    print("=" * 50)
    
    # Load existing articles
    news_path = Path(__file__).parent.parent / "news.json"
    existing_data = load_existing_news(news_path)
    existing_urls = get_existing_urls(existing_data)
    print(f"Loaded existing news.json ({len(existing_urls)} articles)")
    
    # Scrape new articles
    new_articles = scrape_all_sources(existing_urls)
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
