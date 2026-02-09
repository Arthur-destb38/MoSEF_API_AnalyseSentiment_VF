#!/usr/bin/env bash
# =============================================================================
# Scrape toutes les plateformes en une fois (Reddit, StockTwits, Twitter,
# YouTube, Telegram, 4chan, Bitcointalk, GitHub, Bluesky).
# Les posts sont enregistrés en base (.env / DATABASE_URL ou SQLite).
# Peut prendre longtemps (plusieurs dizaines de minutes selon les limites).
# =============================================================================

set -e
cd "$(dirname "$0")"
PROJECT_DIR=$(pwd)

# Activer le venv si présent
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Charger .env (le script Python le charge aussi, mais au cas où)
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

echo "Lancement du scrape depuis $PROJECT_DIR"
echo "  (pour un run sans Selenium, lancez : ./scrape_all.sh --http-only)"
echo ""

python scripts/scrape_all.py "$@"

echo ""
echo "Terminé."
