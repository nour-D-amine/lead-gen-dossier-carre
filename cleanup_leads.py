"""
cleanup_leads.py — Nettoyage de la base de leads existante
Filtre les leads NAF 41.20B, sans site, domaine exclu ou sans email.
Met à jour le CSV local et synchronise avec Google Sheets.
"""

import csv
import os
import logging
from pathlib import Path
from urllib.parse import urlparse

import config
from utils.web_search import EXCLUDED_DOMAINS
from utils.google_sheets_sync import push_to_google_sheets

# Configurer le logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger("cleanup")

def clean_leads_csv():
    csv_path = Path(config.CSV_PATH)
    if not csv_path.exists():
        logger.warning(f"Aucun fichier CSV trouvé à {csv_path}")
        return

    logger.info(f"Chargement des leads existants depuis {csv_path}...")
    
    # Charger tous les leads
    leads = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            leads.append(row)

    total_initial = len(leads)
    logger.info(f"Nombre initial de leads : {total_initial}")

    # Filtrer les leads
    cleaned_leads = []
    for lead in leads:
        nom = lead.get("Nom", "")
        siren = lead.get("SIREN", "")
        naf = lead.get("NAF", "").strip()
        site = lead.get("Site Web", "").strip()
        email = lead.get("Email", "").strip()

        # 1. Filtrer les codes NAF hors cible (Alerte de dérive)
        target_nafs = [
            "41.20B", "43.99C", "43.91A", "43.91B", "43.21A", "43.22A", "43.22B",
            "43.32A", "43.32B", "43.31Z", "43.34Z", "43.99A", "42.11Z",
            "42.21Z", "43.12A"
        ]
        if naf not in target_nafs:
            logger.info(f"Lead '{nom}' ({siren}) supprimé : code NAF hors cible ({naf}).")
            continue

        # 2. Filtrer les leads sans site web
        if not site:
            logger.info(f"Lead '{nom}' ({siren}) supprimé : aucun site web.")
            continue

        # 2.5 Filtrer par mots-clés d'exclusion dans le nom (Alerte de dérive)
        from utils.api_annuaire import _normaliser_texte
        nom_normalise = _normaliser_texte(nom)
        if any(_normaliser_texte(kw) in nom_normalise for kw in config.EXCLUDED_KEYWORDS):
            logger.info(f"Lead '{nom}' ({siren}) supprimé : mot-clé exclu dans le nom.")
            continue

        # 3. Filtrer les domaines exclus
        domain = urlparse(site).netloc.lower()
        if any(excl in domain for excl in EXCLUDED_DOMAINS):
            logger.info(f"Lead '{nom}' ({siren}) supprimé : domaine exclu ({domain}).")
            continue

        # 4. Filtrer les leads sans email
        if not email:
            logger.info(f"Lead '{nom}' ({siren}) supprimé : aucun email de contact.")
            continue

        # Le lead est qualifié
        cleaned_leads.append(lead)

    total_final = len(cleaned_leads)
    logger.info(f"Nombre final de leads qualifiés : {total_final} ({total_initial - total_final} supprimés)")

    # Réécrire le CSV
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=config.CSV_COLUMNS)
        writer.writeheader()
        for lead in cleaned_leads:
            # S'assurer que les clés correspondent aux colonnes du CSV
            writer.writerow({col: lead.get(col, "") for col in config.CSV_COLUMNS})

    logger.info(f"Fichier CSV local mis à jour avec succès.")

    # Synchroniser avec Google Sheets
    logger.info("Synchronisation avec Google Sheets en cours...")
    success = push_to_google_sheets(
        config.GOOGLE_CREDENTIALS_PATH,
        config.GOOGLE_SHEET_NAME,
        config.CSV_PATH
    )
    if success:
        logger.info("Synchronisation Google Sheets réussie.")
    else:
        logger.error("Échec de la synchronisation Google Sheets.")

if __name__ == "__main__":
    clean_leads_csv()
