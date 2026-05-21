import re
import logging
import urllib.parse

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

BASE_URL = "https://api.firecrawl.dev/v1/scrape"


def _has_email(text: str) -> bool:
    """Vérifie si le texte contient au moins une adresse email légitime."""
    if not text:
        return False
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = re.findall(pattern, text)
    valid_emails = [
        e for e in emails 
        if not any(dummy in e.lower() for dummy in ["sentry.io", "wix.com", "example.com", "bootstrap", "wixpress", "schema.org", "png", "jpg", "jpeg", "gif", "svg"])
    ]
    return len(valid_emails) > 0


def _extract_sub_links(markdown: str, base_url: str) -> list[str]:
    """Extrait des liens pertinents (contact, mentions légales, à propos) du markdown."""
    if not markdown:
        return []
    
    pattern = r"\[([^\]]+)\]\(([^)]+)\)"
    matches = re.findall(pattern, markdown)
    
    keywords = ["contact", "mention", "legale", "legal", "propos", "about"]
    sub_links = []
    
    for text, link_url in matches:
        text_lower = text.lower()
        url_lower = link_url.lower()
        
        if any(kw in text_lower or kw in url_lower for kw in keywords):
            full_url = urllib.parse.urljoin(base_url, link_url)
            try:
                base_domain = urllib.parse.urlparse(base_url).netloc.lower()
                link_domain = urllib.parse.urlparse(full_url).netloc.lower()
                # S'assurer qu'on reste sur le même site et éviter les doublons
                if base_domain == link_domain and full_url not in sub_links:
                    sub_links.append(full_url)
            except Exception:
                continue
                
    # Prioriser les liens contenant "contact"
    sub_links.sort(key=lambda x: 0 if "contact" in x.lower() else 1)
    return sub_links


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=3, max=15),
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectTimeout)),
)
def _call_scrape_api(client: httpx.Client, limiter: RateLimiter, api_key: str, url: str) -> str:
    """Effectue l'appel HTTP unitaire vers Firecrawl Scrape."""
    limiter.wait()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "url": url,
        "formats": ["markdown"],
        "onlyMainContent": False,
        "waitFor": 1000,
    }

    try:
        response = client.post(BASE_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        limiter.on_success()

        data = response.json()
        return data.get("data", {}).get("markdown", "")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            limiter.on_rate_limit()
        elif e.response.status_code == 402:
            logger.error("Firecrawl: crédits épuisés (402)")
            return ""
        else:
            limiter.on_error()
        raise
    except Exception:
        limiter.on_error()
        raise


def scrape_website_markdown(
    client: httpx.Client,
    limiter: RateLimiter,
    api_key: str,
    url: str,
) -> str:
    """Scrape un site web en profondeur (Homepage + Contact en fallback) pour maximiser les chances de trouver l'email."""
    if not url or not api_key:
        return ""
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    if not limiter.has_budget():
        logger.warning("Firecrawl: budget de crédits épuisé")
        return ""

    logger.info(f"Firecrawl: grattage page d'accueil -> {url}")
    try:
        homepage_markdown = _call_scrape_api(client, limiter, api_key, url)
    except Exception as e:
        logger.warning(f"Firecrawl: échec du grattage pour {url}: {e}")
        return ""

    if not homepage_markdown:
        return ""

    # Si la page d'accueil contient déjà un email valide, on s'arrête là pour préserver les crédits
    if _has_email(homepage_markdown):
        logger.info(f"Firecrawl: Email détecté sur la page d'accueil de {url}")
        return homepage_markdown

    # Sinon, on cherche des sous-pages stratégiques
    sub_links = _extract_sub_links(homepage_markdown, url)
    if not sub_links:
        return homepage_markdown

    # Gratter la page la plus prometteuse (ex: contact)
    target_sub_link = sub_links[0]
    logger.info(f"Firecrawl: Aucun email sur l'accueil, tentative de grattage de la page contact -> {target_sub_link}")
    
    try:
        sub_markdown = _call_scrape_api(client, limiter, api_key, target_sub_link)
        if sub_markdown:
            # Concaténer les deux contenus pour que l'intelligence artificielle et nos regex y accèdent
            combined_markdown = f"{homepage_markdown}\n\n--- PAGE DE CONTACT/MENTIONS ---\n\n{sub_markdown}"
            logger.info(f"Firecrawl: Grattage de la sous-page réussi et fusionné.")
            return combined_markdown
    except Exception as e:
        logger.warning(f"Firecrawl: échec du grattage de la sous-page {target_sub_link}: {e}")

    return homepage_markdown

