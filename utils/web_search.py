import logging
import re
from duckduckgo_search import DDGS
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

EXCLUDED_DOMAINS = [
    "pappers.fr", "societe.com", "pagesjaunes.fr", "annuaire-entreprises.data.gouv.fr",
    "linkedin.com", "facebook.com", "instagram.com", "kompass.com", "mappy.com",
    "verif.com", "infonet.fr", "rubypayeur.com", "societeinfo.com", "manageo.fr",
    "actu.fr", "ouest-france.fr", "lefigaro.fr", "lemonde.fr", "wikipedia.org"
]

def clean_company_name(name: str) -> str:
    """
    Nettoie les noms d'entreprises complexes (ex: avec des parenthèses ou des slashes multiples)
    pour optimiser la recherche web.
    """
    if not name:
        return ""
    
    # 1. Enlever tout ce qui est entre parenthèses si la partie avant est assez longue
    main_part = name.split("(")[0].strip()
    if len(main_part) >= 3:
        # Si la partie principale contient des slashes, prendre le premier
        return main_part.split("/")[0].strip()
        
    # 2. Si la partie avant est trop courte (ex: "C (...)"), on regarde dans les parenthèses
    match = re.search(r'\((.*?)\)', name)
    if match:
        inner = match.group(1)
        # Prendre le premier élément séparé par un slash
        parts = [p.strip() for p in inner.split("/") if p.strip()]
        if parts and len(parts[0]) >= 3:
            return parts[0]
            
    # 3. Repli : nettoyer les caractères spéciaux et renvoyer
    return name.replace("(", "").replace(")", "").replace("/", " ").strip()

def find_company_website(company_name: str) -> str:
    """
    Cherche le site web d'une entreprise via DuckDuckGo.
    Exclut les annuaires d'entreprises connus et les sites d'actualités.
    """
    if not company_name:
        return ""
        
    try:
        cleaned_name = clean_company_name(company_name)
        logger.info(f"Recherche site web pour '{company_name}' -> Nettoyé: '{cleaned_name}'")
        
        # Recherche flexible focusée BTP France
        query = f"{cleaned_name} entreprise BTP site officiel"
        results = DDGS().text(query, region='fr-fr', max_results=10)
        
        for res in results:
            url = res.get("href", "")
            if not url:
                continue
            
            domain = urlparse(url).netloc.lower()
            
            # Vérifier si c'est un domaine exclu
            is_excluded = any(excl in domain for excl in EXCLUDED_DOMAINS)
            if not is_excluded:
                logger.info(f"Site officiel trouvé pour {cleaned_name} : {url}")
                return url
                
        logger.debug(f"Aucun site pertinent trouvé pour {cleaned_name}")
        return ""
    except Exception as e:
        logger.warning(f"Erreur DuckDuckGo pour {company_name}: {e}")
        return ""
