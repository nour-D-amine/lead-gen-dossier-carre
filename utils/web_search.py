import logging
from duckduckgo_search import DDGS
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

EXCLUDED_DOMAINS = [
    "pappers.fr", "societe.com", "pagesjaunes.fr", "annuaire-entreprises.data.gouv.fr",
    "linkedin.com", "facebook.com", "instagram.com", "kompass.com", "mappy.com",
    "verif.com", "infonet.fr", "rubypayeur.com", "societeinfo.com", "manageo.fr"
]

def find_company_website(company_name: str) -> str:
    """
    Cherche le site web d'une entreprise via DuckDuckGo.
    Exclut les annuaires d'entreprises connus.
    """
    if not company_name:
        return ""
        
    try:
        # Recherche avec un focus sur la France
        query = f'"{company_name}" entreprise BTP site web'
        results = DDGS().text(query, region='fr-fr', max_results=10)
        
        for res in results:
            url = res.get("href", "")
            if not url:
                continue
            
            domain = urlparse(url).netloc.lower()
            
            # Vérifier si c'est un annuaire à exclure
            is_excluded = any(excl in domain for excl in EXCLUDED_DOMAINS)
            if not is_excluded:
                logger.info(f"Site web trouvé pour {company_name} : {url}")
                return url
                
        logger.debug(f"Aucun site pertinent trouvé pour {company_name}")
        return ""
    except Exception as e:
        logger.warning(f"Erreur DuckDuckGo pour {company_name}: {e}")
        return ""
