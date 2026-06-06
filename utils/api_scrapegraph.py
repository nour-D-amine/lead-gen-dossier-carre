import re
import logging
import urllib.parse

from scrapegraphai.graphs import SmartScraperGraph

from utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


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


def _build_graph_config(api_key: str) -> dict:
    """Construit la configuration ScrapegraphAI avec Gemini comme LLM backend."""
    return {
        "llm": {
            "api_key": api_key,
            "model": "google_genai/gemini-2.0-flash",
        },
        "verbose": False,
        "headless": True,
    }


def _scrape_page(api_key: str, url: str) -> str:
    """Scrape une page unique via ScrapegraphAI et retourne le contenu en markdown."""
    graph_config = _build_graph_config(api_key)

    scraper = SmartScraperGraph(
        prompt=(
            "Extrais le contenu complet de cette page web en markdown propre. "
            "Inclus tous les textes, titres, paragraphes, liens, adresses email, "
            "numéros de téléphone et informations de contact. "
            "Conserve la structure avec les titres markdown (##, ###). "
            "Retourne le résultat sous la clé 'markdown_content'."
        ),
        source=url,
        config=graph_config,
    )

    result = scraper.run()

    if isinstance(result, dict):
        return result.get("markdown_content", str(result))
    return str(result) if result else ""


def scrape_website_markdown(
    limiter: RateLimiter,
    api_key: str,
    url: str,
) -> str:
    """
    Scrape un site web en profondeur (Homepage + Contact en fallback)
    pour maximiser les chances de trouver l'email.

    Utilise ScrapegraphAI avec Gemini comme LLM backend.
    """
    if not url or not api_key:
        return ""
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    logger.info(f"ScrapegraphAI: grattage page d'accueil -> {url}")
    limiter.wait()
    try:
        homepage_markdown = _scrape_page(api_key, url)
        limiter.on_success()
    except Exception as e:
        limiter.on_error()
        logger.warning(f"ScrapegraphAI: échec du grattage pour {url}: {e}")
        return ""

    if not homepage_markdown:
        return ""

    # Si la page d'accueil contient déjà un email valide, on s'arrête là
    if _has_email(homepage_markdown):
        logger.info(f"ScrapegraphAI: Email détecté sur la page d'accueil de {url}")
        return homepage_markdown

    # Sinon, on cherche des sous-pages stratégiques
    sub_links = _extract_sub_links(homepage_markdown, url)
    if not sub_links:
        return homepage_markdown

    # Gratter la page la plus prometteuse (ex: contact)
    target_sub_link = sub_links[0]
    logger.info(f"ScrapegraphAI: Aucun email sur l'accueil, tentative de grattage de la page contact -> {target_sub_link}")

    limiter.wait()
    try:
        sub_markdown = _scrape_page(api_key, target_sub_link)
        limiter.on_success()
        if sub_markdown:
            # Concaténer les deux contenus pour que l'IA et nos regex y accèdent
            combined_markdown = f"{homepage_markdown}\n\n--- PAGE DE CONTACT/MENTIONS ---\n\n{sub_markdown}"
            logger.info(f"ScrapegraphAI: Grattage de la sous-page réussi et fusionné.")
            return combined_markdown
    except Exception as e:
        limiter.on_error()
        logger.warning(f"ScrapegraphAI: échec du grattage de la sous-page {target_sub_link}: {e}")

    return homepage_markdown
