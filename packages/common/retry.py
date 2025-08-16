"""
Utilitaires de retry avec backoff exponentiel pour Desktop Agent.

Fournit des décorateurs et fonctions pour retry automatique des opérations.
"""

import asyncio
import functools
import random
import time
from typing import Any, Callable, Optional, Tuple, Type, Union

from .errors import DesktopAgentError, is_retryable_error
from .logging_utils import get_logger

logger = get_logger("retry")


def exponential_backoff(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True
) -> float:
    """
    Calcule le délai d'attente avec backoff exponentiel.
    
    Args:
        attempt: Numéro de tentative (commence à 1)
        base_delay: Délai de base en secondes
        max_delay: Délai maximum en secondes
        exponential_base: Base pour l'exponentielle
        jitter: Ajouter du jitter pour éviter les collisions
        
    Returns:
        Délai d'attente en secondes
    """
    delay = min(base_delay * (exponential_base ** (attempt - 1)), max_delay)
    
    if jitter:
        delay *= (0.5 + random.random() * 0.5)  # Jitter de ±25%
    
    return delay


def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    on_retry: Optional[Callable[[Exception, int], None]] = None
):
    """
    Décorateur pour retry automatique avec backoff exponentiel.
    
    Args:
        max_attempts: Nombre maximum de tentatives
        base_delay: Délai de base entre tentatives
        max_delay: Délai maximum
        exponential_base: Base exponentielle
        jitter: Utiliser le jitter
        retryable_exceptions: Types d'exceptions à retry
        on_retry: Callback appelé lors d'un retry
    """
    if retryable_exceptions is None:
        retryable_exceptions = (Exception,)
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    # Vérifier si l'exception est retryable
                    if not isinstance(e, retryable_exceptions):
                        logger.debug(
                            f"Exception non-retryable: {type(e).__name__}",
                            function=func.__name__,
                            attempt=attempt,
                            error=str(e)
                        )
                        raise
                    
                    # Vérifier avec la logique métier si applicable
                    if isinstance(e, DesktopAgentError) and not is_retryable_error(e):
                        logger.debug(
                            f"Erreur non-retryable selon la logique métier",
                            function=func.__name__,
                            attempt=attempt,
                            error=str(e)
                        )
                        raise
                    
                    # Dernière tentative
                    if attempt == max_attempts:
                        logger.error(
                            f"Échec après {max_attempts} tentatives",
                            function=func.__name__,
                            final_error=str(e)
                        )
                        raise
                    
                    # Calculer le délai et attendre
                    delay = exponential_backoff(
                        attempt, base_delay, max_delay, exponential_base, jitter
                    )
                    
                    logger.warning(
                        f"Tentative {attempt}/{max_attempts} échouée, retry dans {delay:.2f}s",
                        function=func.__name__,
                        attempt=attempt,
                        error=str(e),
                        delay=delay
                    )
                    
                    # Callback de retry si fourni
                    if on_retry:
                        try:
                            on_retry(e, attempt)
                        except Exception as callback_error:
                            logger.warning(
                                f"Erreur dans callback on_retry: {callback_error}",
                                function=func.__name__
                            )
                    
                    time.sleep(delay)
            
            # Ne devrait jamais arriver, mais au cas où
            raise last_exception or RuntimeError("Retry loop error")
        
        return wrapper
    return decorator


def async_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    on_retry: Optional[Callable[[Exception, int], Any]] = None
):
    """
    Décorateur pour retry automatique des fonctions async.
    
    Args:
        max_attempts: Nombre maximum de tentatives
        base_delay: Délai de base entre tentatives
        max_delay: Délai maximum
        exponential_base: Base exponentielle
        jitter: Utiliser le jitter
        retryable_exceptions: Types d'exceptions à retry
        on_retry: Callback async appelé lors d'un retry
    """
    if retryable_exceptions is None:
        retryable_exceptions = (Exception,)
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    # Vérifier si l'exception est retryable
                    if not isinstance(e, retryable_exceptions):
                        logger.debug(
                            f"Exception non-retryable: {type(e).__name__}",
                            function=func.__name__,
                            attempt=attempt,
                            error=str(e)
                        )
                        raise
                    
                    # Vérifier avec la logique métier si applicable
                    if isinstance(e, DesktopAgentError) and not is_retryable_error(e):
                        logger.debug(
                            f"Erreur non-retryable selon la logique métier",
                            function=func.__name__,
                            attempt=attempt,
                            error=str(e)
                        )
                        raise
                    
                    # Dernière tentative
                    if attempt == max_attempts:
                        logger.error(
                            f"Échec après {max_attempts} tentatives",
                            function=func.__name__,
                            final_error=str(e)
                        )
                        raise
                    
                    # Calculer le délai et attendre
                    delay = exponential_backoff(
                        attempt, base_delay, max_delay, exponential_base, jitter
                    )
                    
                    logger.warning(
                        f"Tentative {attempt}/{max_attempts} échouée, retry dans {delay:.2f}s",
                        function=func.__name__,
                        attempt=attempt,
                        error=str(e),
                        delay=delay
                    )
                    
                    # Callback de retry si fourni
                    if on_retry:
                        try:
                            if asyncio.iscoroutinefunction(on_retry):
                                await on_retry(e, attempt)
                            else:
                                on_retry(e, attempt)
                        except Exception as callback_error:
                            logger.warning(
                                f"Erreur dans callback on_retry: {callback_error}",
                                function=func.__name__
                            )
                    
                    await asyncio.sleep(delay)
            
            # Ne devrait jamais arriver, mais au cas où
            raise last_exception or RuntimeError("Retry loop error")
        
        return wrapper
    return decorator


class RetryContext:
    """Contexte pour retry manuel avec statistiques."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        name: str = "operation"
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.name = name
        
        self.current_attempt = 0
        self.total_delay = 0.0
        self.start_time = time.time()
        self.errors: list[Exception] = []
    
    def should_retry(self, error: Exception) -> bool:
        """
        Détermine s'il faut retry après une erreur.
        
        Args:
            error: Exception rencontrée
            
        Returns:
            True s'il faut retry
        """
        self.current_attempt += 1
        self.errors.append(error)
        
        # Vérifier le nombre max de tentatives
        if self.current_attempt >= self.max_attempts:
            logger.error(
                f"Max tentatives atteint pour {self.name}",
                attempts=self.current_attempt,
                total_delay=self.total_delay,
                duration=time.time() - self.start_time
            )
            return False
        
        # Vérifier si l'erreur est retryable
        if isinstance(error, DesktopAgentError) and not is_retryable_error(error):
            logger.debug(
                f"Erreur non-retryable pour {self.name}",
                error_type=type(error).__name__,
                attempt=self.current_attempt
            )
            return False
        
        return True
    
    def wait(self) -> None:
        """Attend selon la stratégie de backoff."""
        delay = exponential_backoff(
            self.current_attempt,
            self.base_delay,
            self.max_delay,
            self.exponential_base,
            self.jitter
        )
        
        self.total_delay += delay
        
        logger.info(
            f"Retry {self.name} dans {delay:.2f}s",
            attempt=self.current_attempt,
            max_attempts=self.max_attempts,
            delay=delay
        )
        
        time.sleep(delay)
    
    async def async_wait(self) -> None:
        """Attend selon la stratégie de backoff (version async)."""
        delay = exponential_backoff(
            self.current_attempt,
            self.base_delay,
            self.max_delay,
            self.exponential_base,
            self.jitter
        )
        
        self.total_delay += delay
        
        logger.info(
            f"Retry {self.name} dans {delay:.2f}s",
            attempt=self.current_attempt,
            max_attempts=self.max_attempts,
            delay=delay
        )
        
        await asyncio.sleep(delay)
    
    def get_stats(self) -> dict[str, Any]:
        """Retourne les statistiques de retry."""
        return {
            "name": self.name,
            "attempts": self.current_attempt,
            "max_attempts": self.max_attempts,
            "total_delay": self.total_delay,
            "duration": time.time() - self.start_time,
            "error_count": len(self.errors),
            "error_types": [type(e).__name__ for e in self.errors]
        }