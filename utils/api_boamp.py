from __future__ import annotations
"""
api_boamp.py — Client API BOAMP OpenDataSoft (Couche 2 — Enrichissement)
Recherche l'activité marchés publics d'une entreprise par son nom.
"""

import logging
from datetime import datetime, timedelta
from urllib.parse import quote

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

BASE_URL = "https://boamp-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/boamp/records"


def _build_where_clause(nom_entreprise: str, months_lookback: int = 24) -> str:
    """
    Construit la clause ODSQL pour rechercher une entreprise dans le BOAMP.

    Args:
        nom_entreprise: Nom de l'entreprise à rechercher
        months_lookback: Nombre de mois à remonter

    Returns:
        Clause WHERE ODSQL
    """
    date_min = (datetime.now() - timedelta(days=months_lookback * 30)).strftime("%Y-%m-%d")

    # Nettoyer le nom : retirer les formes juridiques courantes
    nom_clean = nom_entreprise.upper()
    for suffix in [" SAS", " SARL", " SA", " EURL", " SNC", " SASU", " SCI"]:
        nom_clean = nom_clean.replace(suffix, "")
    nom_clean = nom_clean.strip()

    # Échapper les apostrophes pour ODSQL
    nom_escaped = nom_clean.replace("'", "''")

    return f"search(titulaire,'{nom_escaped}') AND dateparution >= '{date_min}'"


def _summarize_results(records: list[dict], max_items: int = 3) -> str:
    """
    Résume les résultats BOAMP en un texte concis.

    Args:
        records: Liste des enregistrements BOAMP
        max_items: Nombre max de marchés à inclure dans le résumé

    Returns:
        Résumé textuel de l'activité BOAMP
    """
    if not records:
        return "Aucune activité détectée"

    summaries = []
    for record in records[:max_items]:
        objet = record.get("objet", "Objet non précisé")
        date = record.get("dateparution", "")
        nature = record.get("nature_libelle", "")
        acheteur = record.get("nomacheteur", "")

        # Tronquer l'objet si trop long
        if len(objet) > 120:
            objet = objet[:117] + "..."

        parts = []
        if date:
            parts.append(date)
        if nature:
            parts.append(nature)
        if acheteur:
            parts.append(f"pour {acheteur}")
        parts.append(f": {objet}")

        summaries.append(" — ".join(parts) if parts else objet)

    total = len(records)
    result = " | ".join(summaries)

    if total > max_items:
        result += f" | ... et {total - max_items} autre(s) marché(s)"

    return result


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=15),
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectTimeout)),
)
def fetch_activite_boamp(
    client: httpx.Client,
    limiter: RateLimiter,
    nom_entreprise: str,
    months_lookback: int = 24,
    limit: int = 10,
) -> str:
    """
    Recherche l'activité marchés publics d'une entreprise dans le BOAMP.

    Args:
        client: Client httpx réutilisable
        limiter: RateLimiter configuré pour le BOAMP
        nom_entreprise: Nom de l'entreprise
        months_lookback: Mois de recul pour la recherche
        limit: Nombre max de résultats à récupérer

    Returns:
        Résumé textuel de l'activité BOAMP ou "Aucune activité détectée"
    """
    if not nom_entreprise or len(nom_entreprise) < 3:
        return "Aucune activité détectée"

    limiter.wait()

    where_clause = _build_where_clause(nom_entreprise, months_lookback)

    params = {
        "where": where_clause,
        "select": "objet,dateparution,nature_libelle,nomacheteur,titulaire",
        "order_by": "dateparution DESC",
        "limit": limit,
    }

    try:
        response = client.get(BASE_URL, params=params, timeout=15)
        response.raise_for_status()
        limiter.on_success()

        data = response.json()
        total = data.get("total_count", 0)
        records = data.get("results", [])

        logger.debug(
            f"BOAMP '{nom_entreprise}': {total} résultat(s) trouvé(s)"
        )

        return _summarize_results(records)

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            limiter.on_rate_limit()
        else:
            limiter.on_error()
        raise
    except Exception as e:
        limiter.on_error()
        logger.warning(f"BOAMP erreur pour '{nom_entreprise}': {e}")
        return "Aucune activité détectée"
