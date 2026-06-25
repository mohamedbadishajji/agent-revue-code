import time
import os
from functools import wraps
from dotenv import load_dotenv

load_dotenv()

# Configuration du backoff
MAX_RETRIES = 5
INITIAL_WAIT = 1  # secondes
MAX_WAIT = 60     # secondes maximum d'attente


def retry_with_backoff(max_retries: int = MAX_RETRIES, initial_wait: float = INITIAL_WAIT):
    """
    Décorateur qui réessaie automatiquement en cas de rate limit
    REVUE-22 : Backoff exponentiel pour le rate limiting GitHub API
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            wait_time = initial_wait
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)

                except Exception as e:
                    error_str = str(e).lower()

                    # Vérifier si c'est un rate limit
                    is_rate_limit = any(keyword in error_str for keyword in [
                        "rate limit", "403", "429", "abuse", "secondary rate"
                    ])

                    if is_rate_limit:
                        last_exception = e

                        if attempt < max_retries - 1:
                            print(f"   ⚠️ Rate limit détecté — attente {wait_time}s avant réessai ({attempt + 1}/{max_retries})")
                            time.sleep(wait_time)
                            wait_time = min(wait_time * 2, MAX_WAIT)
                        else:
                            print(f"   ❌ Rate limit — nombre maximum de tentatives atteint ({max_retries})")
                            raise last_exception
                    else:
                        raise e

            raise last_exception

        return wrapper
    return decorator


def check_rate_limit(github_client) -> dict:
    """
    Vérifie le quota restant de l'API GitHub
    et attend si nécessaire
    """
    try:
        rate_limit = github_client.get_rate_limit()
        core = rate_limit.resources.core

        remaining = core.remaining
        limit = core.limit
        reset_time = core.reset.timestamp()

        print(f"   📊 GitHub API : {remaining}/{limit} requêtes restantes")

        # Si moins de 100 requêtes restantes → attendre le reset
        if remaining < 100:
            wait_seconds = reset_time - time.time() + 5
            if wait_seconds > 0:
                print(f"   ⚠️ Quota faible ({remaining} restantes) — attente {int(wait_seconds)}s")
                time.sleep(wait_seconds)
                print(f"   ✅ Quota réinitialisé")

        return {
            "remaining": remaining,
            "limit": limit,
            "reset_time": reset_time
        }

    except Exception as e:
        print(f"   ⚠️ Impossible de vérifier le rate limit : {str(e)}")
        return {"remaining": -1, "limit": -1}


def batch_post_comments(post_func, comments: list, batch_size: int = 5, delay: float = 0.5) -> int:
    """
    Poste les commentaires par lots pour éviter le rate limiting
    REVUE-22 : Regroupement des appels API
    """
    posted = 0
    total = len(comments)

    print(f"\n📦 Publication par lots de {batch_size} commentaires...")

    for i in range(0, total, batch_size):
        batch = comments[i:i + batch_size]

        for comment_args in batch:
            try:
                success = post_func(**comment_args)
                if success:
                    posted += 1
            except Exception as e:
                print(f"   ❌ Erreur : {str(e)}")

        # Délai entre les lots pour éviter le rate limiting
        if i + batch_size < total:
            print(f"   ⏳ Pause {delay}s entre les lots...")
            time.sleep(delay)

    print(f"   ✅ {posted}/{total} commentaires postés")
    return posted