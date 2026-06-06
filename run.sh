#!/bin/bash
# ─────────────────────────────────────────────────────────
# run.sh — Script de lancement Lead Gen BTP
# Framework B.L.A.S.T — Dossier Carré
# ─────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Couleurs ─────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Lead Gen BTP — Dossier Carré${NC}"
echo -e "${BLUE}  Framework B.L.A.S.T${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# ── Vérifications ────────────────────────────────────────
if [ ! -f ".env" ]; then
    echo -e "${RED}[ERREUR] Fichier .env manquant.${NC}"
    echo "Créez un fichier .env avec vos clés API :"
    echo "  GEMINI_API_KEY=your-gemini-api-key"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[ERREUR] Python 3 non trouvé.${NC}"
    exit 1
fi

# ── Installation des dépendances si nécessaire ───────────
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}[SETUP] Création de l'environnement virtuel...${NC}"
    python3 -m venv .venv
fi

source .venv/bin/activate

echo -e "${YELLOW}[SETUP] Installation des dépendances...${NC}"
pip install -q -r requirements.txt

# ── Mode d'exécution ─────────────────────────────────────
MODE="${1:-production}"

case "$MODE" in
    dry-run|test)
        echo -e "${YELLOW}[MODE] Dry-run — Aucune API payante ne sera appelée${NC}"
        python3 main.py --dry-run --batch-size 10 --max-leads 50 --max-pages 2
        ;;
    sample)
        echo -e "${YELLOW}[MODE] Sample — 1 code NAF × 1 région${NC}"
        python3 main.py --naf 43.21A --region 11 --batch-size 10 --max-pages 5
        ;;
    production)
        echo -e "${GREEN}[MODE] Production — Pipeline complet${NC}"
        echo -e "${YELLOW}Régions: Toute la France sauf Grand Est${NC}"
        echo -e "${YELLOW}NAF: 35 codes BTP (41xx, 42xx, 43xx)${NC}"
        python3 main.py --batch-size 25
        ;;
    reset)
        echo -e "${RED}[MODE] Reset — Suppression checkpoint et CSV${NC}"
        python3 main.py --reset --dry-run --max-leads 0
        ;;
    *)
        echo -e "${RED}Usage: ./run.sh [dry-run|sample|production|reset]${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}[DONE] Pipeline terminé.${NC}"
echo -e "CSV: ${BLUE}data/leads_btp.csv${NC}"
echo -e "Logs: ${BLUE}logs/${NC}"
