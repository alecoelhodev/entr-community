# T12: Rate limiting with Redis + django-ratelimit

**Status:** ready (the PR stays **draft** until the ⚠ infra steps are done)
**Depends on:** — (MVP done). Infrastructure prerequisites are below.
**User stories:** US-6, US-7, US-11 (abuse protection)

## Goal
Signup, login, reviews and listing writes are rate-limited across all Cloud Run instances. Over the limit, users get a friendly 429 page.

## Context
- Product decision (2026-11-15): use **Redis + django-ratelimit**.
- Cloud Run runs several instances, so counters must live in a shared cache. `django-mongodb-backend` 6.1 has no cache backend, so the shared cache is Redis: Memorystore in production, a compose service locally and in CI.
- Django's built-in `django.core.cache.backends.redis.RedisCache` needs the `redis` (redis-py) package.
- The CI `migrate` step runs on a GitHub runner that can't reach a private Memorystore instance, and it doesn't need a cache.
- Behind Cloud Run, the client IP arrives in `X-Forwarded-For`. **Which entry is trustworthy when a client sends its own XFF is not yet verified.** The assumption is that Google appends the real client IP, making it the rightmost entry. A post-deploy check confirms it (see *Manual verification*).
- Rate limiting was listed as a known launch risk in product.md.

## Acceptance criteria
- **Limits.** POST only; GET/HEAD are never limited. `block=True`.

  | View | Limit | Key |
  |---|---|---|
  | `accounts:login` | 10 / 15 min | client IP |
  | `accounts:login` | 20 / hour | submitted email, lowercased |
  | `accounts:signup` | 5 / hour | client IP |
  | Review create, update, delete | 20 / hour | user |
  | `directory:business_create` | 10 / day | user |
  | `directory:business_edit` | 60 / hour | user |

- **Over the limit:** HTTP 429 rendering `templates/429.html` ("Too many attempts. Try again in a few minutes."). It echoes no request data.
- **Cache settings:** `CACHES["default"]` is `RedisCache(REDIS_URL)` when `REDIS_URL` is set, otherwise `LocMemCache`.
  - When running as a Cloud Run service (`K_SERVICE` is set) without `REDIS_URL`, settings raise `ImproperlyConfigured`. This fails loud in production and leaves the CI `migrate` step and local dev unaffected.
  - django-ratelimit's "cache is not shared" system check is silenced only when the cache is LocMem.
- **TLS to Memorystore:** `REDIS_URL` uses `rediss://` with AUTH. The server CA is mounted from Secret Manager as a file and passed as `ssl_ca_certs`.
- **Client IP:** one key function in `config/ratelimit.py`. It uses the rightmost `X-Forwarded-For` entry and falls back to `REMOTE_ADDR`.
- **Local and CI:** `compose.yaml` gains a pinned `redis` service, and `web` gets `REDIS_URL=redis://redis:6379/0`. The CI test job keeps working through compose.
- **Workflow:**
  - `secrets:` gains `REDIS_URL=entr-redis-url:latest` and a file mount for the CA (`/etc/redis/ca.pem=entr-redis-ca:latest`).
  - `flags:` gains Direct VPC egress: `--network`, `--subnet` and `--vpc-egress=private-ranges-only`, from repo variables. Atlas traffic stays on the public path.

## Tests to write first
`apps/accounts/tests/test_ratelimit.py` → `LoginRateLimitTests`, `SignupRateLimitTests`
- `test_login_ip_limit_returns_429`: the 11th POST from one IP in the window → 429 with the friendly page. A different IP is still allowed.
- `test_login_email_limit_across_ips`.
- `test_signup_ip_limit_returns_429`: the 6th POST → 429.
- `test_get_never_limited`.

`apps/directory/tests/test_ratelimit.py` → `ReviewRateLimitTests`, `ListingRateLimitTests`
- `test_review_user_limit`: the 21st POST → 429. Another user is unaffected.
- `test_business_create_user_limit`.

`config/tests/test_ratelimit_key.py` → `ClientIpKeyTests`
- `test_rightmost_xff_entry_used`.
- `test_spoofed_leading_entry_ignored`.
- `test_remote_addr_fallback`.

`config/tests/test_settings_guard.py` → `RedisGuardTests`
- `test_cloud_run_without_redis_url_raises`: load settings with `K_SERVICE` set and no `REDIS_URL`, in a subprocess or with `importlib.reload` under a patched environment.

Call `cache.clear()` in `setUp` wherever limits matter, so tests don't leak counts into each other.

## Implementation notes
- **Dependencies:** verify before pinning.
  - Check `django-ratelimit` (4.x as far as known) and `redis` on PyPI and in their issue trackers, including Django 6.1 compatibility.
  - Add both to `pyproject.toml` with version ranges, run `docker compose exec web uv lock`, rebuild, and give a one-line rationale in the PR.
  - **If django-ratelimit doesn't support Django 6.1, stop and ask.** The fallback is about 30 lines of fixed-window limiter on the same cache (`cache.add` + `cache.incr`).
- **429 handling:** `django_ratelimit.middleware.RatelimitMiddleware` plus `RATELIMIT_VIEW = "config.views.ratelimited"`.
- **Login view:** login uses Django's `LoginView`, so wrap it in `apps/accounts/urls.py` with stacked `ratelimit(...)` decorators. The email key is a callable that lowercases `request.POST["username"]`.
- **⚠ confirm: human infra steps.** You run these, before the PR leaves draft. Document them in `docs/deployment.md`.
  1. Create a Memorystore for Redis instance: Basic tier, smallest size, same region as Cloud Run, AUTH enabled, in-transit encryption enabled. It has a monthly cost; the PR states the current list price.
  2. Create secret `entr-redis-url` (`rediss://:<AUTH>@<IP>:6378/0`) and secret `entr-redis-ca` (the server CA from `gcloud redis instances describe`). Grant `roles/secretmanager.secretAccessor` on both to the runtime service account.
  3. Grant the deploy principal (WIF) `roles/compute.networkUser` on the subnet. Set the repo variables for network and subnet.
- **Docs:**
  - `.env.example`: `REDIS_URL`.
  - CLAUDE.md: config, the compose Redis, the `K_SERVICE` guard, and where limits are declared.

## Out of scope
- CAPTCHA.
- Per-endpoint admin tuning UI.
- Rate limiting read-only endpoints (the map API).
- WAF / Cloud Armor.

## Manual verification
- **Local, with the compose Redis:** 11 login POSTs → the 11th returns 429. `docker compose exec redis redis-cli --scan --pattern '*rl*'` shows the counters.
- **After deploy, the empirical XFF check:** send 11 login POSTs to production, each with a different spoofed `X-Forwarded-For` value. If the 11th returns 429, the key correctly ignores client-supplied XFF. If not, fix the key function before announcing the launch.
- The deploy smoke test still passes.
