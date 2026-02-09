# 🕵️ Mystery Story Bot

Bot automatisé qui scrape des histoires mystérieuses/creepy de Reddit via Bright Data, génère des scripts narratifs de 30 secondes avec GPT-4o, et envoie des fiches de production sur Discord.

## Architecture

```
Reddit (4 subreddits)
    ↓  Bright Data Web Unlocker
Scraping + Filtrage (score 30-200, dédup SQLite)
    ↓
GPT-4o (script 130-150 mots + 5-6 keywords visuels)
    ↓
SQLite (stockage avec ID unique)
    ↓
Discord Webhook (fiche de production)
    ↓
[Manuel] Sélection d'un script par ID
    ↓
OpenAI TTS (voix Onyx) → MP3
```

## Prérequis

- Python 3.12+
- Clés API : OpenAI, Bright Data (Web Unlocker), Discord Webhook

## Installation locale

```bash
cd mystery-story-bot

# Créer un environnement virtuel
python -m venv .venv
source .venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt

# Configurer les variables d'environnement
cp .env.example .env
# Éditer .env avec tes clés
```

## Configuration (.env)

| Variable | Description | Défaut |
|---|---|---|
| `OPENAI_API_KEY` | Clé API OpenAI | — (requis) |
| `BRIGHTDATA_API_KEY` | Bearer token Bright Data | — (requis) |
| `BRIGHTDATA_ZONE` | Nom de la zone Web Unlocker | — (requis) |
| `DISCORD_WEBHOOK_URL` | URL du webhook Discord | — (requis) |
| `DB_PATH` | Chemin vers la BDD SQLite | `data/stories.db` |
| `OUTPUT_DIR` | Dossier pour les MP3 | `output` |
| `SUBREDDITS` | Liste séparée par virgules | `UnresolvedMysteries,HighStrangeness,TheGrittyPast,OddlyTerrifying` |
| `MIN_SCORE` | Score Reddit minimum | `30` |
| `MAX_SCORE` | Score Reddit maximum | `200` |
| `MAX_STORIES_PER_RUN` | Limite d'histoires par exécution | `5` |

## Utilisation

### 1. Lancer le pipeline (scrape → generate → notify)

```bash
python -m src.main
```

Le bot va :
1. Scraper les 4 subreddits via Bright Data
2. Filtrer par score (30-200) et contenu non vide
3. Vérifier les doublons en BDD (par `reddit_id`)
4. Générer un script de 30s et des keywords visuels via GPT-4o
5. Sauvegarder en base SQLite
6. Envoyer une fiche de production sur Discord avec l'ID en BDD

### 2. Générer le TTS (après sélection manuelle)

```bash
python -m src.tts --id 42
```

→ Génère un MP3 avec la voix Onyx d'OpenAI et l'envoie sur Discord.

## Déploiement Docker (VPS)

### Build & run une fois

```bash
docker compose build
docker compose run --rm mystery-bot
```

### TTS via Docker

```bash
docker compose run --rm mystery-bot python -m src.tts --id 42
```

### Cron quotidien (sur le VPS)

Ajouter au crontab de l'hôte :

```bash
crontab -e
```

```
0 8 * * * cd /path/to/mystery-story-bot && docker compose run --rm mystery-bot >> /var/log/mystery-bot.log 2>&1
```

→ Exécution quotidienne à 8h00. Le container se lance, traite, notifie, puis s'arrête.

## Coûts estimés par exécution

| Service | Consommation | Estimation |
|---|---|---|
| Bright Data | ~4 requêtes (1/subreddit × 3 feeds) | ~$0.01-0.05 |
| OpenAI GPT-4o | ~5 appels (MAX_STORIES_PER_RUN) | ~$0.05-0.10 |
| OpenAI TTS | 0 (à la demande seulement) | ~$0.01/appel |
| **Total/jour** | | **~$0.10-0.15** |

## Subreddits ciblés

| Subreddit | Contenu |
|---|---|
| r/UnresolvedMysteries | Affaires non résolues, documenté |
| r/HighStrangeness | Phénomènes inexpliqués, UFO, paranormal |
| r/TheGrittyPast | Archives historiques sombres |
| r/OddlyTerrifying | Visuels et concepts dérangeants |

## Structure du projet

```
mystery-story-bot/
├── .env.example          # Template des variables
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── README.md
├── src/
│   ├── __init__.py
│   ├── config.py         # Chargement config
│   ├── db.py             # SQLite CRUD
│   ├── scraper.py        # Bright Data + Reddit
│   ├── generator.py      # GPT-4o scripts
│   ├── discord_notify.py # Webhook Discord
│   ├── main.py           # Orchestrateur
│   └── tts.py            # CLI TTS
├── data/                 # BDD SQLite
└── output/               # MP3 générés
```
