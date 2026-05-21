from __future__ import annotations
"""
rate_limiter.py — Gestionnaire de rate limiting adaptatif
Respecte les quotas gratuits de chaque API.
"""

import time
import logging
from threading import Lock
from typing import Optional

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Throttle adaptatif avec backoff exponentiel sur erreurs 429.
    Thread-safe grâce au Lock.
    """

    def __init__(self, name: str, min_delay: float, max_requests: Optional[int] = None):
        """
        Args:
            name: Nom de l'API (pour les logs)
            min_delay: Délai minimum entre requêtes (en secondes)
            max_requests: Quota max de requêtes (None = illimité)
        """
        self.name = name
        self.min_delay = min_delay
        self.max_requests = max_requests
        self._request_count = 0
        self._last_request_time = 0.0
        self._current_delay = min_delay
        self._lock = Lock()

    @property
    def request_count(self) -> int:
        return self._request_count

    @property
    def remaining_requests(self) -> Optional[int]:
        if self.max_requests is None:
            return None
        return max(0, self.max_requests - self._request_count)

    def has_budget(self) -> bool:
        """Vérifie s'il reste du budget de requêtes."""
        if self.max_requests is None:
            return True
        return self._request_count < self.max_requests

    def wait(self) -> None:
        """
        Attend le délai nécessaire avant la prochaine requête.
        Lève RuntimeError si le quota est épuisé.
        """
        with self._lock:
            if not self.has_budget():
                raise RuntimeError(
                    f"[{self.name}] Quota épuisé : {self._request_count}/{self.max_requests} requêtes"
                )

            elapsed = time.monotonic() - self._last_request_time
            if elapsed < self._current_delay:
                sleep_time = self._current_delay - elapsed
                logger.debug(f"[{self.name}] Throttle: attente {sleep_time:.2f}s")
                time.sleep(sleep_time)

            self._last_request_time = time.monotonic()
            self._request_count += 1

            if self._request_count % 50 == 0:
                remaining = self.remaining_requests
                remaining_str = f"{remaining} restantes" if remaining is not None else "illimité"
                logger.info(
                    f"[{self.name}] {self._request_count} requêtes effectuées ({remaining_str})"
                )

    def on_success(self) -> None:
        """Réinitialise immédiatement le délai après un succès pour reprendre à pleine vitesse."""
        with self._lock:
            if self._current_delay > self.min_delay:
                self._current_delay = self.min_delay
                logger.debug(f"[{self.name}] Backoff réinitialisé au minimum: {self._current_delay:.2f}s")

    def on_rate_limit(self) -> None:
        """Double le délai après un 429 (backoff exponentiel, plafonné à 60s)."""
        with self._lock:
            self._current_delay = min(60.0, self._current_delay * 2)
            logger.warning(
                f"[{self.name}] Rate limit 429 → backoff: {self._current_delay:.2f}s"
            )

    def on_error(self) -> None:
        """Augmente légèrement le délai après une erreur."""
        with self._lock:
            self._current_delay = min(30.0, self._current_delay * 1.5)
            logger.warning(
                f"[{self.name}] Erreur API → délai ajusté: {self._current_delay:.2f}s"
            )

    def reset(self) -> None:
        """Remet le compteur à zéro."""
        with self._lock:
            self._request_count = 0
            self._current_delay = self.min_delay
            self._last_request_time = 0.0

    def __repr__(self) -> str:
        remaining = self.remaining_requests
        remaining_str = f"{remaining}" if remaining is not None else "∞"
        return (
            f"RateLimiter(name={self.name!r}, "
            f"requests={self._request_count}, "
            f"remaining={remaining_str}, "
            f"delay={self._current_delay:.2f}s)"
        )
