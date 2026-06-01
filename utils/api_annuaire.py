from __future__ import annotations
"""
api_annuaire.py — Client API Annuaire Entreprises (Couche 1 — Data Ingestion)
Endpoint public, sans clé API.
"""

import logging
import unicodedata
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from utils.rate_limiter import RateLimiter
import config

logger = logging.getLogger(__name__)


def _normaliser_texte(texte: str) -> str:
    """
    Convertit en minuscules et supprime les accents pour une comparaison robuste.
    """
    if not texte:
        return ""
    nfkd_form = unicodedata.normalize('NFKD', texte.lower())
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

BASE_URL = "https://recherche-entreprises.api.gouv.fr/search"

# Qualités de dirigeants à prioriser pour identifier le dirigeant principal
QUALITES_PRIORITAIRES = [
    "Président",
    "Gérant",
    "Directeur Général",
    "Président du conseil d'administration",
    "Président du conseil d'administration et directeur général",
    "Président de SAS",
    "Président directeur général",
    "Chef d'entreprise",
    "Co-gérant",
]


def _extraire_dirigeant_principal(dirigeants: list[dict]) -> str:
    """
    Extrait le nom du dirigeant principal depuis la liste retournée par l'API.
    Priorise les qualités de direction (Président, Gérant, DG).
    Ne retient que les personnes physiques.
    """
    if not dirigeants:
        return ""

    # Filtrer les personnes physiques uniquement
    personnes = [d for d in dirigeants if d.get("type_dirigeant") == "personne physique"]
    if not personnes:
        return ""

    # Chercher par qualité prioritaire
    for qualite_cible in QUALITES_PRIORITAIRES:
        for d in personnes:
            qualite = (d.get("qualite") or "").strip()
            if qualite_cible.lower() in qualite.lower():
                prenom = (d.get("prenoms") or "").strip().title()
                nom = (d.get("nom") or "").strip().title()
                # Nettoyer les noms entre parenthèses (nom de naissance)
                if "(" in nom:
                    nom = nom.split("(")[0].strip()
                return f"{prenom} {nom}".strip()

    # Fallback : prendre la première personne physique
    d = personnes[0]
    prenom = (d.get("prenoms") or "").strip().title()
    nom = (d.get("nom") or "").strip().title()
    if "(" in nom:
        nom = nom.split("(")[0].strip()
    return f"{prenom} {nom}".strip()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectTimeout)),
)
def fetch_page(
    client: httpx.Client,
    limiter: RateLimiter,
    naf_code: str,
    region: str,
    page: int,
    per_page: int = 25,
) -> dict:
    """
    Récupère une page de résultats de l'API Annuaire Entreprises.

    Args:
        client: Client httpx réutilisable
        limiter: RateLimiter configuré pour l'Annuaire
        naf_code: Code NAF (ex: "43.21A")
        region: Code région INSEE (ex: "11" pour IDF)
        page: Numéro de page (1-indexed)
        per_page: Résultats par page (max 25)

    Returns:
        dict avec "results", "total_results", "total_pages"
    """
    limiter.wait()

    params = {
        "activite_principale": naf_code,
        "region": region,
        "page": page,
        "per_page": per_page,
    }

    try:
        response = client.get(BASE_URL, params=params, timeout=15)
        response.raise_for_status()
        limiter.on_success()
        return response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            limiter.on_rate_limit()
            raise
        elif e.response.status_code == 400:
            logger.warning(f"Rejet 400 (Bad Request) pour NAF={naf_code}. Code NAF possiblement invalide ou refusé par l'API.")
            return {"results": [], "total_results": 0, "total_pages": 0}
        else:
            limiter.on_error()
            raise
    except Exception as e:
        limiter.on_error()
        raise


def parse_entreprise(raw: dict, categories_exclues: set[str] | None = None) -> dict | None:
    """
    Parse un résultat brut de l'API en dictionnaire lead normalisé.
    Retourne None si l'entreprise doit être filtrée.

    Args:
        raw: Résultat brut de l'API
        categories_exclues: Set de catégories à exclure (ex: {"GE"})

    Returns:
        dict avec clés: siren, nom, naf, dirigeant, adresse, ca, categorie
        ou None si filtré
    """
    # Filtrer les entreprises fermées
    if raw.get("etat_administratif") != "A":
        return None

    # Filtrer par catégorie
    categorie = raw.get("categorie_entreprise", "")
    if categories_exclues and categorie in categories_exclues:
        return None

    # Filtrer les entreprises non diffusibles
    if raw.get("statut_diffusion") != "O":
        return None

    siren = raw.get("siren", "")
    if not siren or len(siren) != 9:
        return None

    # Filtrer par mots-clés d'exclusion dans le nom (Avatar Client / ICP)
    nom = raw.get("nom_complet", "").strip()
    nom_normalise = _normaliser_texte(nom)
    for kw in config.EXCLUDED_KEYWORDS:
        kw_normalise = _normaliser_texte(kw)
        if kw_normalise in nom_normalise:
            logger.debug(f"Lead '{nom}' filtré par mot-clé d'exclusion ICP ('{kw}').")
            return None

    # Extraire le dirigeant principal
    dirigeants = raw.get("dirigeants", [])
    dirigeant = _extraire_dirigeant_principal(dirigeants)

    # Extraire le siège pour l'adresse
    siege = raw.get("siege", {})

    # Extraire le CA si disponible
    finances = raw.get("finances", {})
    ca = None
    if finances:
        # Prendre l'année la plus récente
        derniere_annee = max(finances.keys()) if finances else None
        if derniere_annee:
            ca = finances[derniere_annee].get("ca")

    return {
        "siren": siren,
        "nom": raw.get("nom_complet", "").strip(),
        "naf": raw.get("activite_principale", ""),
        "dirigeant": dirigeant,
        "adresse": siege.get("adresse", ""),
        "code_postal": siege.get("code_postal", ""),
        "commune": siege.get("libelle_commune", ""),
        "departement": siege.get("departement", ""),
        "categorie": categorie,
        "ca": ca,
        "effectif": raw.get("tranche_effectif_salarie", ""),
    }


def fetch_all_for_naf_region(
    client: httpx.Client,
    limiter: RateLimiter,
    naf_code: str,
    region: str,
    max_pages: int | None = None,
    categories_exclues: set[str] | None = None,
) -> list[dict]:
    """
    Récupère toutes les entreprises pour un code NAF × région.
    Pagine automatiquement.

    Args:
        client: Client httpx
        limiter: RateLimiter
        naf_code: Code NAF
        region: Code région
        max_pages: Limite de pages (None = toutes)
        categories_exclues: Catégories à exclure

    Returns:
        Liste de leads parsés
    """
    leads = []
    page = 1

    # Premier appel pour connaître le total
    data = fetch_page(client, limiter, naf_code, region, page)
    total_results = data.get("total_results", 0)
    total_pages = data.get("total_pages", 0)

    if total_results == 0:
        logger.debug(f"NAF {naf_code} × Région {region}: 0 résultats")
        return []

    logger.info(
        f"NAF {naf_code} × Région {region}: {total_results} entreprises ({total_pages} pages)"
    )

    # Parser la première page
    for raw in data.get("results", []):
        lead = parse_entreprise(raw, categories_exclues)
        if lead:
            leads.append(lead)

    # Paginer le reste
    effective_max = total_pages
    if max_pages is not None:
        effective_max = min(total_pages, max_pages)

    for page in range(2, effective_max + 1):
        try:
            data = fetch_page(client, limiter, naf_code, region, page)
            for raw in data.get("results", []):
                lead = parse_entreprise(raw, categories_exclues)
                if lead:
                    leads.append(lead)
        except Exception as e:
            logger.error(f"Erreur page {page} NAF {naf_code} Région {region}: {e}")
            break

    logger.info(f"NAF {naf_code} × Région {region}: {len(leads)} leads retenus")
    return leads
