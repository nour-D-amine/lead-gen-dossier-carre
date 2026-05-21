from __future__ import annotations
"""
api_firecrawl.py — Client API Firecrawl (Couche 2 — Enrichissement)
Scrape les sites web des entreprises pour extraire les emails de contact.
"""

import re
import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

BASE_URL = "https://api.firecrawl.dev/v1/scrape"


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=3, max=15),
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectTimeout)),
)
def scrape_website_markdown(
    client: httpx.Client,
    limiter: RateLimiter,
    api_key: str,
    url: str,
) -> str:
    """Scrape un site web pour en extraire le Markdown brut (1 crédit/page)."""
    if not url or not api_key:
        return ""
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    if not limiter.has_budget():
        logger.warning("Firecrawl: budget de crédits épuisé")
        return ""

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
        content = data.get("data", {}).get("markdown", "")
        if not content:
            return ""

        logger.debug(f"Firecrawl: markdown extrait pour {url} ({len(content)} chars)")
        return content

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            limiter.on_rate_limit()
        elif e.response.status_code == 402:
            logger.error("Firecrawl: crédits épuisés (402)")
            return ""
        else:
            limiter.on_error()
        raise
    except Exception as e:
        limiter.on_error()
        logger.warning(f"Firecrawl erreur pour {url}: {e}")
        return ""
