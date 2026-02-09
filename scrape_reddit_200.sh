#!/usr/bin/env bash
# =============================================================================
# Reddit : 200 posts par crypto (r/cryptocurrency, r/bitcoin, r/ethereum,
#          r/solana, r/cardano). Enregistrement en base (Supabase ou SQLite).
# Les doublons sont automatiquement ignorés.
# Compatible : macOS, Linux (Bash).
# =============================================================================

set -e
cd "$(dirname "$0")"

if [ -d ".venv" ]; then
    source .venv/bin/activate
fi
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

echo "Reddit — 200 posts par crypto → base de données"
echo ""
python scripts/scrape_reddit_200.py
echo ""
echo "Terminé."
