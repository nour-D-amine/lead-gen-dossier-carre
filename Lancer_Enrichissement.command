#!/bin/bash
# Script de lancement de l'enrichissement - Dossier Carré

# Se déplacer dans le dossier du projet
cd "$(dirname "$0")"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Lancement de l'Enrichissement IA - Dossier Carré"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Lancer la pipeline
./run.sh production

echo ""
echo "Appuyez sur Entrée pour fermer cette fenêtre..."
read
