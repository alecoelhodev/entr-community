"""Fixed-window POST rate limits on the shared cache (Redis in production)."""

import hashlib
import logging
import re
import time
from functools import wraps

from django.core.cache import cache
from django.shortcuts import render

logger = logging.getLogger(__name__)

_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def client_ip(request):
    # Cloud Run appends the address it saw as the rightmost X-Forwarded-For entry; anything left of it is client-supplied.
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return forwarded.rsplit(",", 1)[-1].strip() or request.META.get("REMOTE_ADDR", "")


def user_key(request):
    return str(request.user.pk)


def ratelimit(group, key, rate):
    """Allow `rate` ("10/15m", "5/h", "10/d") POSTs per key(request) per window; return a 429 page beyond it.

    A key returning a falsy value skips the limit. Put it inside @login_required when keying on the user.
    """
    count, multiplier, unit = re.fullmatch(r"(\d+)/(\d*)([smhd])", rate).groups()
    limit, period = int(count), int(multiplier or 1) * _UNITS[unit]

    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method == "POST" and _over_limit(group, key(request), limit, period):
                return render(request, "429.html", status=429)
            return view(request, *args, **kwargs)

        return wrapped

    return decorator


def _over_limit(group, value, limit, period):
    if not value:
        return False
    # Hashed so emails and IPs aren't stored in the cache.
    digest = hashlib.sha256(value.encode()).hexdigest()[:32]
    cache_key = f"rl:{group}:{digest}:{int(time.time()) // period}"
    try:
        cache.add(cache_key, 0, period)
        hits = cache.incr(cache_key)
    except ValueError:  # Expired between add and incr.
        cache.set(cache_key, 1, period)
        hits = 1
    except Exception:
        # Fail open: a cache outage shouldn't take logins down. Logged server-side for alerting.
        logger.exception("Rate-limit cache unavailable; allowing request")
        return False
    return hits > limit
