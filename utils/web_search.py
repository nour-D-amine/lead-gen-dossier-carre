import logging
import re
import httpx
from duckduckgo_search import DDGS
from urllib.parse import urlparse
import config

logger = logging.getLogger(__name__)

EXCLUDED_DOMAINS = [
    # Annuaires administratifs, juridiques et d'entreprises
    "pappers.fr", "societe.com", "pagesjaunes.fr", "annuaire-entreprises.data.gouv.fr",
    "kompass.com", "mappy.com", "verif.com", "infonet.fr", "rubypayeur.com",
    "societeinfo.com", "manageo.fr", "infogreffe.fr", "bodacc.fr", "societe.ninja",
    "lecese.fr", "service-public.fr", "economie.gouv.fr", "entreprendre.service-public.fr",
    "entreprendre.service-public.gouv.fr", "guichet-unique.fr", "formalites.entreprises.gouv.fr",
    "inpi.fr", "data.gouv.fr", "annuaire-entreprises.data.gouv.fr", "mon-entreprise.urssaf.fr",
    "urssaf.fr", "infonet.fr", "societego.com", "laconstruction.fr", "le-repertoire.fr",
    "cohesion-territoires.gouv.fr", "marches-publics.gouv.fr", "boamp.fr", "legifrance.gouv.fr",
    "steinertriples.ch", "jorfsearch.steinertriples.ch", "verif-siret.fr", "sirene.fr",
    "numtvagratuit.com", "nomatagratuit.com", "koalt.fr", "societeinfo.com",
    # Plateformes sociales, de communication et professionnelles
    "linkedin.com", "facebook.com", "instagram.com", "twitter.com", "x.com",
    "pinterest.com", "youtube.com", "vimeo.com", "tiktok.com", "medium.com",
    # Actualités, média et presse
    "actu.fr", "ouest-france.fr", "lefigaro.fr", "lemonde.fr", "wikipedia.org", "lesechos.fr",
    "lesechos", "bfmtv.com", "usinenouvelle.com", "paperjam.lu", "pleinevie.fr",
    "lavoixdunord.fr", "leparisien.fr", "liberation.fr", "la-croix.com", "mediapart.fr",
    "capital.fr", "challenges.fr", "lexpress.fr", "lepoint.fr", "nouvelobs.com",
    # Emplois et recrutement
    "indeed.com", "hellowork.com", "monster.fr", "pole-emploi.fr", "francetravail.fr", "emploipublic.fr",
    "glassdoor.fr", "cadremploi.fr", "apec.fr",
    # Organismes de BTP, fédérations, caisses et annuaires sectoriels
    "cibtp.fr", "capeb.fr", "ffbatiment.fr", "fntp.fr", "probtp.com", "preventionbtp.fr",
    "ccca-btp.fr", "prevbtp.fr", "qualibat.com", "qualifelec.fr", "certibat.fr",
    "federation-francaise-experts-batiments.fr", "batiweb.com", "batiactu.com",
    "lemoniteur.fr", "travaux.com", "habitatpresto.com", "123travaux.com", "quotatis.fr",
    # Domaines génériques, moteurs de recherche et technologies tiers
    "google.com", "google.fr", "google.de", "translate.google", "yahoo.com", "bing.com", "baidu.com",
    "wellsfargo.com", "duckduckgo.com", "wixpress.com", "wix.com", "wordpress.com", "wordpress.org",
    "github.com", "mil.wf", "play.tetris.com", "sg.fr", "credit-agricole.fr", "banquepopulaire.fr",
    "caisse-epargne.fr", "bnpparibas.fr", "societegenerale.fr", "cic.fr", "lcl.fr", "creditmutuel.fr",
    "contract-factory.com", "legalstart.fr", "captaincontract.com", "vt.edu", "drhouse-immo.com",
    "iadfrance.fr", "century21.fr", "orpi.com", "laforet.com", "foncia.com"
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
    Recherche le site web d'une entreprise via DuckDuckGo Search.
    Exclut les annuaires d'entreprises connus, les sites d'actualités et les réseaux sociaux.
    """
    if not company_name:
        return ""
        
    cleaned_name = clean_company_name(company_name)
    logger.info(f"Recherche site web pour '{company_name}' -> Nettoyé: '{cleaned_name}'")
    
    # Recherche flexible focusée BTP France
    query = f"{cleaned_name} entreprise BTP site officiel"
    
    # Recherche via DuckDuckGo Search
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

