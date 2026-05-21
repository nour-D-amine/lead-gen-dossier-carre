from __future__ import annotations
"""
api_gemini.py — Client LLM via Google GenAI (Gemini)
Analyse les frictions, extrait l'email, et rédige les cold emails personnalisés.
"""

import json
import logging
from google import genai
from google.genai import types

from config import GEMINI_MODEL, SYSTEM_PROMPT_PATH
from utils.rate_limiter import RateLimiter
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

_system_prompt_cache: str | None = None

def _load_system_prompt() -> str:
    global _system_prompt_cache
    if _system_prompt_cache is None:
        with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
            _system_prompt_cache = f.read().strip()
    return _system_prompt_cache

def _build_user_message(lead: dict) -> str:
    context = {
        "siren": lead.get("siren", ""),
        "nom": lead.get("nom", ""),
        "naf": lead.get("naf", ""),
        "dirigeant": lead.get("dirigeant", ""),
        "commune": lead.get("commune", ""),
        "departement": lead.get("departement", ""),
        "activite_boamp": lead.get("activite_boamp", "Aucune activité détectée"),
        "site_markdown": lead.get("site_markdown", ""),
    }
    return json.dumps(context, ensure_ascii=False, indent=2)

@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, min=3, max=30))
def analyze_and_draft(
    client: genai.Client,
    limiter: RateLimiter,
    lead: dict,
) -> tuple[str, str, str]:
    """
    Analyse les frictions d'un lead, rédige un cold email personnalisé,
    et extrait l'email de contact depuis le Markdown du site web.

    Returns:
        Tuple (analyse_friction, draft_email, email_contact)
    """
    limiter.wait()
    system_prompt = _load_system_prompt()
    user_message = _build_user_message(lead)

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                types.Part.from_text(text=system_prompt),
                types.Part.from_text(text=user_message),
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        limiter.on_success()

        raw_content = response.text
        if not raw_content:
            logger.warning(f"Gemini: réponse vide pour {lead.get('siren', '?')}")
            return "", "", ""
        
        raw_output = raw_content.strip()

        try:
            parsed = json.loads(raw_output)
            analyse = parsed.get("analyse_friction", "")
            email = parsed.get("draft_email", "")
            contact = parsed.get("email_contact", "")
        except json.JSONDecodeError:
            analyse = raw_output
            email = ""
            contact = ""
            logger.warning(f"Gemini: réponse non-JSON pour {lead.get('siren', '?')}")

        logger.debug(f"Gemini: analyse terminée pour {lead.get('nom', '?')}")
        return analyse, email, contact

    except Exception as e:
        if "429" in str(e):
            limiter.on_rate_limit()
            logger.warning("Gemini: rate limit atteint, on re-tente...")
            raise
        elif "503" in str(e):
            logger.warning("Gemini: Erreur 503 (Surcharge Google), on re-tente...")
            raise
        else:
            limiter.on_error()
            logger.error(f"Gemini erreur pour {lead.get('siren', '?')}: {e}")
        return "", "", ""

def analyze_batch(
    client: genai.Client,
    limiter: RateLimiter,
    leads: list[dict],
) -> list[tuple[str, str, str]]:
    """Traite un batch de leads séquentiellement."""
    results = []
    for i, lead in enumerate(leads):
        logger.info(f"Gemini: traitement lead {i+1}/{len(leads)} — {lead.get('nom', '?')}")
        try:
            analyse, email, contact = analyze_and_draft(client, limiter, lead)
        except Exception as e:
            logger.error(f"Gemini: Échec définitif pour {lead.get('nom', '?')} après 4 tentatives ({type(e).__name__})")
            analyse, email, contact = "", "", ""
        results.append((analyse, email, contact))
    return results
