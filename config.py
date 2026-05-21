"""
config.py — Configuration & Constantes
Lead Gen BTP — Dossier Carré
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Chargement .env ──────────────────────────────────────────────
load_dotenv()

# ── Clés API ─────────────────────────────────────────────────────
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# ── Chemins ──────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
PROMPTS_DIR = PROJECT_ROOT / "prompts"

# ── Google Sheets ──────────────────────────────────────────────────
GOOGLE_CREDENTIALS_PATH = os.path.join(PROJECT_ROOT, "credentials.json")

# En production (ex: Railway), si le fichier n'existe pas mais la variable d'env est fournie, on le crée à la volée
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON", "")
if GOOGLE_CREDS_JSON and not os.path.exists(GOOGLE_CREDENTIALS_PATH):
    try:
        import json
        creds_dict = json.loads(GOOGLE_CREDS_JSON)
        with open(GOOGLE_CREDENTIALS_PATH, "w", encoding="utf-8") as f:
            json.dump(creds_dict, f, indent=2)
    except Exception as e:
        print(f"Erreur d'écriture de credentials.json depuis la variable d'environnement : {e}")

GOOGLE_SHEET_NAME = "CRM Dossier Carré"

CSV_PATH = DATA_DIR / "leads_btp.csv"
CHECKPOINT_PATH = DATA_DIR / "checkpoint.json"
SYSTEM_PROMPT_PATH = PROMPTS_DIR / "system_prompt.txt"

# Création des dossiers si nécessaire
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
PROMPTS_DIR.mkdir(exist_ok=True)

# ── Codes NAF BTP (41xx, 42xx, 43xx) ────────────────────────────
NAF_CODES = [
    # 41 — Promotion immobilière & Construction de bâtiments
    "41.10A", "41.10B", "41.10C", "41.10D",
    "41.20A", "41.20B",
    # 42 — Génie civil
    "42.11Z", "42.12Z", "42.13A", "42.13B",
    "42.21Z", "42.22Z", "42.91Z", "42.99Z",
    # 43 — Travaux de construction spécialisés
    "43.11Z", "43.12A", "43.12B", "43.13Z",
    "43.21A", "43.22A", "43.22B", "43.29A",
    "43.31Z", "43.32A", "43.32B", "43.33Z",
    "43.34Z", "43.39Z",
    "43.91A", "43.91B",
    "43.99A", "43.99B", "43.99C", "43.99D", "43.99E",
]

# ── Régions ciblées (toute la France SAUF Grand Est = 44) ────────
# Codes INSEE des régions françaises
REGIONS = [
    "11",  # Île-de-France
    "24",  # Centre-Val de Loire
    "27",  # Bourgogne-Franche-Comté
    "28",  # Normandie
    "32",  # Hauts-de-France
    # "44" — Grand Est → EXCLU
    "52",  # Pays de la Loire
    "53",  # Bretagne
    "75",  # Nouvelle-Aquitaine
    "76",  # Occitanie
    "84",  # Auvergne-Rhône-Alpes
    "93",  # Provence-Alpes-Côte d'Azur
    "94",  # Corse
]

# ── Catégories d'entreprise ciblées ──────────────────────────────
# TPE = pas de catégorie spécifique dans l'API (effectif < 10)
# PME = PME, ETI = ETI
# On inclut toutes les catégories sauf GE (Grandes Entreprises)
CATEGORIES_EXCLUES = {"GE"}

# ── Rate Limits ──────────────────────────────────────────────────
RATE_LIMITS = {
    "annuaire": {
        "min_delay": 0.2,       # 200ms → ~5 req/s (marge sous les 7/s)
        "max_requests": None,   # Pas de quota mensuel
    },
    "boamp": {
        "min_delay": 0.5,       # 500ms → 2 req/s (conservateur)
        "max_requests": None,   # Pas de quota
    },
    "firecrawl": {
        "min_delay": 2.0,       # 2s entre chaque requête
        "max_requests": 1000,   # 1000 crédits/mois
    },
    "gemini": {
        "min_delay": 2.0,       # 2s entre chaque appel
        "max_requests": None,   # Dépend du tier
    },
}

# ── Paramètres de batch ──────────────────────────────────────────
DEFAULT_BATCH_SIZE = 25          # Leads traités par batch
GEMINI_BATCH_SIZE = 10           # Leads envoyés à Gemini par appel
ANNUAIRE_PER_PAGE = 25           # Max autorisé par l'API
BOAMP_MONTHS_LOOKBACK = 24       # Recherche BOAMP sur les 24 derniers mois

# ── CSV Colonnes ─────────────────────────────────────────────────
CSV_COLUMNS = [
    "SIREN",
    "Nom",
    "NAF",
    "Dirigeant",
    "Email",
    "Site Web",
    "Activité BOAMP",
    "Analyse Friction",
    "Draft Email",
    "Statut Traitement",
]

# ── Modèle LLM (Gemini) ──────────────────────────────────────
GEMINI_MODEL = "gemini-2.5-flash"
LLM_MAX_TOKENS = 4096

# ── Logging ──────────────────────────────────────────────────────
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
