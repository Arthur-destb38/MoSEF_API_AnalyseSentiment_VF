#!/bin/bash
# =============================================================================
# Crypto Sentiment Dashboard - Script d'installation et de lancement
# =============================================================================
# Compatible : macOS, Linux (tout système avec Bash et python3).
# Windows : utiliser WSL, Git Bash, ou "python -m venv .venv" puis
#           ".venv\Scripts\activate" et "streamlit run streamlit_app.py".
# =============================================================================

set -e

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Se placer dans le dossier du script
cd "$(dirname "$0")"
PROJECT_DIR=$(pwd)

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║          Crypto Sentiment Dashboard - Setup                  ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# =============================================================================
# 1. Vérifier Python
# =============================================================================
echo -e "${YELLOW}[1/5] Vérification de Python...${NC}"

if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    
    if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 10 ]; then
        echo -e "${GREEN}✓ Python $PYTHON_VERSION détecté${NC}"
    else
        echo -e "${RED}✗ Python 3.10+ requis (trouvé: $PYTHON_VERSION)${NC}"
        exit 1
    fi
else
    echo -e "${RED}✗ Python3 non trouvé. Installez Python 3.10+${NC}"
    exit 1
fi

# =============================================================================
# 2. Créer le fichier .env si nécessaire
# =============================================================================
echo -e "${YELLOW}[2/5] Configuration de l'environnement...${NC}"

if [ ! -f ".env" ]; then
    echo -e "${BLUE}Création du fichier .env...${NC}"
    cat > .env << 'EOF'
# =============================================================================
# Configuration Crypto Sentiment Dashboard
# =============================================================================

# Mot de passe pour accéder au dashboard (optionnel, laisser vide pour accès libre)
# APP_PASSWORD=votre_mot_de_passe

# Base de données PostgreSQL (optionnel, utilise SQLite par défaut)
# DATABASE_URL=postgresql://user:password@localhost:5432/crypto_sentiment

# =============================================================================
# APIs (optionnel - pour les scrapers avancés)
# =============================================================================

# Twitter/X (pour le scraper Twitter)
# TWITTER_USERNAME=
# TWITTER_PASSWORD=

# YouTube Data API
# YOUTUBE_API_KEY=

# GitHub Personal Access Token
# GITHUB_TOKEN=

# Bluesky
# BLUESKY_HANDLE=
# BLUESKY_APP_PASSWORD=

EOF
    echo -e "${GREEN}✓ Fichier .env créé${NC}"
else
    echo -e "${GREEN}✓ Fichier .env existant${NC}"
fi

# =============================================================================
# 3. Créer l'environnement virtuel
# =============================================================================
echo -e "${YELLOW}[3/5] Configuration de l'environnement virtuel...${NC}"

if [ ! -d ".venv" ]; then
    echo -e "${BLUE}Création du venv...${NC}"
    python3 -m venv .venv
    echo -e "${GREEN}✓ Environnement virtuel créé${NC}"
else
    echo -e "${GREEN}✓ Environnement virtuel existant${NC}"
fi

# Activer le venv pour ce script
source .venv/bin/activate

# =============================================================================
# 4. Installer les dépendances
# =============================================================================
echo -e "${YELLOW}[4/5] Installation des dépendances...${NC}"

# Upgrade pip
pip install --upgrade pip -q

# Essayer d'abord avec Poetry si disponible
if command -v poetry &> /dev/null; then
    echo -e "${BLUE}Installation via Poetry...${NC}"
    poetry install --no-interaction
elif [ -f ".venv/bin/poetry" ]; then
    echo -e "${BLUE}Installation via Poetry (venv)...${NC}"
    .venv/bin/poetry install --no-interaction
else
    echo -e "${BLUE}Installation via pip...${NC}"
    
    # Installer les dépendances principales
    pip install -q \
        streamlit \
        pandas \
        numpy \
        plotly \
        python-dotenv \
        selenium \
        beautifulsoup4 \
        lxml \
        requests \
        transformers \
        torch \
        statsmodels \
        undetected-chromedriver \
        google-api-python-client \
        psycopg2-binary \
        instaloader \
        atproto \
        fastapi \
        uvicorn \
        jinja2
fi

echo -e "${GREEN}✓ Dépendances installées${NC}"

# =============================================================================
# 5. Lancer Streamlit
# =============================================================================
echo -e "${YELLOW}[5/5] Lancement de l'application...${NC}"

# Trouver un port disponible
PORT=8501
while lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; do
    PORT=$((PORT + 1))
    if [ $PORT -gt 8600 ]; then
        echo -e "${RED}✗ Aucun port disponible entre 8501 et 8600${NC}"
        exit 1
    fi
done

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Application prête !                                         ║${NC}"
echo -e "${GREEN}║                                                              ║${NC}"
echo -e "${GREEN}║  URL: ${BLUE}http://localhost:${PORT}${GREEN}                                  ║${NC}"
echo -e "${GREEN}║                                                              ║${NC}"
echo -e "${GREEN}║  Appuyez sur Ctrl+C pour arrêter                             ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Lancer Streamlit
exec .venv/bin/python -m streamlit run streamlit_app.py --server.port $PORT
