#!/bin/bash
# Script de lancement du Dashboard - Dossier Carré

# Se déplacer dans le dossier du projet
cd "$(dirname "$0")"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Démarrage du Dashboard Lead Gen - Dossier Carré"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Vérifier si l'environnement virtuel existe
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Démarrer le serveur
python3 dashboard_server.py
