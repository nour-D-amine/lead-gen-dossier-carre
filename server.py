"""
server.py — Moteur d'Extraction BTP · Dossier Carré
FastAPI + ScrapeGraphAI (Gemini) → Déployé sur Railway / Cloud Run.
Reçoit une URL depuis le flux Antigravity, scrape, analyse, et renvoie
les données prospect + brouillon cold email.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
import os
import logging
import re
import json
import asyncio

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LOGGING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger("dossier-carre-engine")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# APP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
app = FastAPI(
    title="Dossier Carré — Moteur d'Extraction BTP",
    description="Scrape un site d'entreprise BTP et renvoie les données prospect + cold email.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["*"],
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MODÈLES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class AnalyseRequest(BaseModel):
    url: str


class ProspectResponse(BaseModel):
    statut: str
    nom: str = ""
    dirigeant: str = ""
    email: str = ""
    siren: str = ""
    naf: str = ""
    activite: str = ""
    site_web: str = ""
    certifications: str = ""
    chantier_recent: str = ""
    analyse_friction: str = ""
    draft_email: str = ""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PROMPT D'EXTRACTION — Aligné sur l'avatar client Dossier Carré
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROMPT_EXTRACTION = """
Tu es un analyste commercial expert du secteur BTP français.
Analyse ce site web d'entreprise du bâtiment et extrais les informations suivantes.
Réponds UNIQUEMENT en JSON valide, sans texte autour.

{
  "nom": "Nom complet de l'entreprise (raison sociale)",
  "dirigeant": "Nom et prénom du dirigeant / gérant si mentionné",
  "email": "Adresse email de contact professionnelle (pas de noreply, pas de webmaster)",
  "siren": "Numéro SIREN si visible (9 chiffres)",
  "naf": "Code NAF / APE si visible",
  "activite": "Description courte de l'activité principale (gros œuvre, couverture, etc.)",
  "certifications": "Certifications obtenues (RGE, Qualibat, ISO, etc.) séparées par des virgules",
  "chantier_recent": "Référence de chantier récent le plus précis possible",
  "specialite": "Domaine de spécialité principal"
}

Règles strictes :
- Si une information n'est pas trouvée, utilise une chaîne vide "".
- Pour l'email, cherche dans les pages Contact, Mentions légales, et le footer.
- Priorise les emails de type contact@, info@, direction@ — jamais de noreply@.
- Le SIREN fait exactement 9 chiffres.
"""

PROMPT_COLD_EMAIL = """
Tu es un rédacteur commercial pour l'agence Dossier Carré (https://dossier-carre.fr/).
Dossier Carré propose aux artisans et PME du BTP un dossier complet prêt à déposer
pour répondre aux appels d'offres publics : DC1, DC2, mémoire technique, annexes.

Rédige un cold email ultra-personnalisé pour le prospect ci-dessous.
Contexte prospect : {context}

Règles de style (ton Apple, institutionnel, minimaliste) :
- 5 à 7 phrases maximum.
- Vouvoiement obligatoire.
- Aucun superlatif, aucun emoji, aucune urgence artificielle.
- Accroche = une friction concrète identifiée sur leur site ou leur activité.
- Un seul CTA clair en fin de message.
- Signature : L'équipe Dossier Carré

Réponds en JSON :
{{
  "analyse_friction": "La friction administrative identifiée en 1-2 phrases.",
  "draft_email": "Le texte complet du cold email prêt à envoyer."
}}
"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# UTILITAIRES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _extract_json(text: str) -> dict:
    """Extrait le premier bloc JSON d'un texte brut (robuste aux ```json ... ```)."""
    if not text:
        return {}
    # Tenter un parse direct
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Chercher un bloc ```json ... ```
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # Chercher le premier { ... }
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return {}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ENDPOINTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@app.get("/")
async def health():
    return {"status": "ok", "service": "Dossier Carré — Moteur d'Extraction BTP", "version": "1.0.5"}


@app.post("/analyser", response_model=ProspectResponse)
async def analyser_site(request: AnalyseRequest):
    """
    Pipeline en 2 passes :
      1. ScrapeGraphAI → Extraction des données brutes du prospect
      2. ScrapeGraphAI → Rédaction du cold email personnalisé
    """
    logger.info(f"Nouvelle analyse demandée : {request.url}")

    # ── Vérification clé API ──
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        logger.error("GEMINI_API_KEY manquante.")
        raise HTTPException(status_code=500, detail="Clé API Gemini manquante sur le serveur.")

    try:
        from scrapegraphai.graphs import SmartScraperGraph

        graph_config = {
            "llm": {
                "api_key": gemini_key,
                "model": "google_genai/gemini-1.5-flash",
            },
            "verbose": False,
        }

        # ━━━ PASSE 1 : Extraction des données prospect ━━━
        logger.info("Passe 1 — Extraction des données prospect...")
        scraper_extract = SmartScraperGraph(
            prompt=PROMPT_EXTRACTION,
            source=request.url,
            config=graph_config,
        )
        raw_result = await asyncio.to_thread(scraper_extract.run)
        logger.info(f"Passe 1 terminée. Type: {type(raw_result)}")

        # Normaliser la réponse (peut être dict ou str)
        if isinstance(raw_result, str):
            prospect = _extract_json(raw_result)
        elif isinstance(raw_result, dict):
            prospect = raw_result
        else:
            prospect = {}

        nom = prospect.get("nom", "")
        dirigeant = prospect.get("dirigeant", "")
        email = prospect.get("email", "")
        siren = prospect.get("siren", "")
        naf = prospect.get("naf", "")
        activite = prospect.get("activite", prospect.get("specialite", ""))
        certifications = prospect.get("certifications", "")
        chantier = prospect.get("chantier_recent", "")

        logger.info(f"Prospect extrait : {nom} | Email: {email} | SIREN: {siren}")

        # ━━━ PASSE 2 : Rédaction du cold email ━━━
        context_str = json.dumps({
            "nom": nom,
            "dirigeant": dirigeant,
            "activite": activite,
            "certifications": certifications,
            "chantier_recent": chantier,
            "url": request.url,
        }, ensure_ascii=False)

        prompt_email = PROMPT_COLD_EMAIL.format(context=context_str)

        logger.info("Passe 2 — Rédaction du cold email...")
        scraper_email = SmartScraperGraph(
            prompt=prompt_email,
            source=request.url,
            config=graph_config,
        )
        raw_email = await asyncio.to_thread(scraper_email.run)
        logger.info(f"Passe 2 terminée. Type: {type(raw_email)}")

        if isinstance(raw_email, str):
            email_data = _extract_json(raw_email)
        elif isinstance(raw_email, dict):
            email_data = raw_email
        else:
            email_data = {}

        analyse_friction = email_data.get("analyse_friction", "")
        draft_email = email_data.get("draft_email", "")

        # ━━━ Réponse finale ━━━
        return ProspectResponse(
            statut="succès",
            nom=nom,
            dirigeant=dirigeant,
            email=email,
            siren=siren,
            naf=naf,
            activite=activite,
            site_web=request.url,
            certifications=certifications,
            chantier_recent=chantier,
            analyse_friction=analyse_friction,
            draft_email=draft_email,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erreur lors de l'analyse de {request.url}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur d'extraction : {str(e)}",
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# POINT D'ENTRÉE — uvicorn
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
