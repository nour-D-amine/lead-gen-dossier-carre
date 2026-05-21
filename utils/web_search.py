import logging
import re
import httpx
from duckduckgo_search import DDGS
from urllib.parse import urlparse
import config

logger = logging.getLogger(__name__)

EXCLUDED_DOMAINS = [
    # Annuaires administratifs et d'entreprises
    "pappers.fr", "societe.com", "pagesjaunes.fr", "annuaire-entreprises.data.gouv.fr",
    "kompass.com", "mappy.com", "verif.com", "infonet.fr", "rubypayeur.com",
    "societeinfo.com", "manageo.fr", "infogreffe.fr", "bodacc.fr", "societe.ninja",
    "lecese.fr", "service-public.fr", "economie.gouv.fr", "entreprendre.service-public.fr",
    # Plateformes sociales et professionnelles
    "linkedin.com", "facebook.com", "instagram.com", "twitter.com", "x.com",
    "pinterest.com", "youtube.com",
    # Actualités et média
    "actu.fr", "ouest-france.fr", "lefigaro.fr", "lemonde.fr", "wikipedia.org",
    # Emplois
    "indeed.com", "hellowork.com", "monster.fr", "pole-emploi.fr", "francetravail.fr", "emploipublic.fr",
    # Organismes de BTP (non spécifiques à une seule entreprise)
    "cibtp.fr", "capeb.fr", "ffbatiment.fr", "fntp.fr",
    # Domaines génériques / Fallbacks de blocage ou d'exemples
    "google.com", "yahoo.com", "bing.com", "baidu.com", "wellsfargo.com", "duckduckgo.com",
    "wixpress.com", "wix.com", "wordpress.com", "github.com"
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
    Cherche le site web d'une entreprise.
    Tente d'abord via Firecrawl Search (Google + proxies résidentiels, robuste dans le cloud).
    En cas d'échec ou d'absence de clé, repli sur DuckDuckGo (local uniquement, bloqué sur Railway).
    Exclut les annuaires d'entreprises connus, les sites d'actualités et les réseaux sociaux.
    """
    if not company_name:
        return ""
        
    cleaned_name = clean_company_name(company_name)
    logger.info(f"Recherche site web pour '{company_name}' -> Nettoyé: '{cleaned_name}'")
    
    # Recherche flexible focusée BTP France
    query = f"{cleaned_name} entreprise BTP site officiel"
    
    # 1. Tentative principale via Firecrawl Search
    if config.FIRECRAWL_API_KEY:
        try:
            logger.info(f"Tentative Firecrawl Search pour: '{query}'")
            headers = {
                "Authorization": f"Bearer {config.FIRECRAWL_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "query": query,
                "limit": 5
            }
            
            # Utilisation d'un client httpx temporaire pour appeler l'API de recherche Firecrawl
            with httpx.Client() as client:
                response = client.post(
                    "https://api.firecrawl.dev/v1/search",
                    json=payload,
                    headers=headers,
                    timeout=20
                )
                
            if response.status_code == 200:
                res_data = response.json()
                if res_data.get("success") and res_data.get("data"):
                    for item in res_data["data"]:
                        url = item.get("url", "")
                        if not url:
                            continue
                        
                        domain = urlparse(url).netloc.lower()
                        is_excluded = any(excl in domain for excl in EXCLUDED_DOMAINS)
                        if not is_excluded:
                            logger.info(f"Site officiel trouvé (Firecrawl) pour {cleaned_name} : {url}")
                            return url
                else:
                    logger.warning(f"Firecrawl Search a renvoyé du JSON invalide ou success=False: {res_data}")
            else:
                logger.warning(f"Firecrawl Search a échoué avec le code statut {response.status_code}: {response.text}")
                
        except Exception as e:
            logger.warning(f"Erreur lors de la recherche Firecrawl pour {cleaned_name}: {e}. Passage au repli DDG...")
            
    # 2. Repli secondaire via DuckDuckGo Search (DDG)
    try:
        logger.info(f"Passage au repli DuckDuckGo pour: '{query}'")
        results = DDGS().text(query, region='fr-fr', max_results=10)
        
        for res in results:
            url = res.get("href", "")
            if not url:
                continue
            
            domain = urlparse(url).netloc.lower()
            is_excluded = any(excl in domain for excl in EXCLUDED_DOMAINS)
            if not is_excluded:
                logger.info(f"Site officiel trouvé (DuckDuckGo) pour {cleaned_name} : {url}")
                return url
                
        logger.debug(f"Aucun site pertinent trouvé (DDG) pour {cleaned_name}")
        return ""
    except Exception as e:
        logger.warning(f"Erreur DuckDuckGo pour {company_name}: {e}")
        return ""


def search_company_email(company_name: str) -> list[str]:
    """
    Recherche l'email de l'entreprise via une recherche web ciblée.
    Extrait les emails des snippets des résultats de recherche DuckDuckGo.
    """
    if not company_name:
        return []
        
    cleaned_name = clean_company_name(company_name)
    query = f'"{cleaned_name}" BTP (email OR contact OR "@")'
    logger.info(f"Recherche d'email web ciblée pour: '{query}'")
    emails = []
    
    try:
        results = DDGS().text(query, region='fr-fr', max_results=8)
        for res in results:
            text = f"{res.get('title', '')} {res.get('body', '')}"
            # Extraction par regex
            found = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
            for email in found:
                email_lower = email.lower().strip()
                # Nettoyage ponctuation de fin
                while email_lower and email_lower[-1] in ['.', ',', ';', ':', '!', '?']:
                    email_lower = email_lower[:-1]
                if "@" in email_lower and email_lower not in emails:
                    # Écarter les faux positifs évidents
                    if not any(dummy in email_lower for dummy in ["sentry.io", "wix.com", "example.com", "bootstrap", "wixpress", "schema.org", "png", "jpg", "jpeg", "gif", "svg"]):
                        emails.append(email_lower)
        if emails:
            logger.info(f"Emails trouvés via recherche web pour {cleaned_name}: {emails}")
    except Exception as e:
        logger.warning(f"Erreur DDG lors de la recherche d'email pour {company_name}: {e}")
        
    return emails

