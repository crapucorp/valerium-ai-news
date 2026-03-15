# OhVali News Scraper

Scraper automatique pour le site ohvali.com (actualités IA).

## Stack
- **Scraping:** RSS feeds (10 sources) + Brave Search API
- **Résumés:** Gemini CLI (`gemini -p`)
- **Images:** og:image ou Brave Image Search fallback
- **Filtre:** Uniquement articles liés à l'IA (mots-clés obligatoires)
- **Hot News:** Scoring basé sur trends Twitter/Reddit + keywords prioritaires

## Config
- **Cron:** 8h France tous les jours
- **GitHub:** SSH deploy key (`~/.ssh/ohvali_deploy`)
- **Repo:** `crapucorp/valerium-ai-news`

## Lancement manuel
```bash
cd /home/ubuntu/.openclaw/workspace/ia-news/scraper
bash deploy.sh
```

## Historique
- 2026-03-15: Migration Mistral → Gemini CLI pour les résumés
- 2026-03-15: Migration HTTPS token → SSH deploy key pour GitHub push
