# T01: Accounts: custom user, signup, login

**Status:** ready
**Depends on:** —
**User stories:** US-6

## Goal
Visitors can sign up and log in with email and password. The project uses a custom user model from now on.

## Context
- The project uses Django's default `auth.User`. Its migrations live in `mongo_migrations/auth/`, registered in `MIGRATION_MODULES` (`config/settings.py`). Contrib apps use ObjectId AppConfigs from `config/apps.py`.
- Swapping `AUTH_USER_MODEL` after `admin` migrations have been applied raises `InconsistentMigrationHistory`. Both the local and production databases already have them applied. Neither holds real data (production has no users or places).

## Acceptance criteria
- **Given** a visitor on `/accounts/signup/`, **when** they submit a valid email, name and password (twice), **then** a user is created, they're logged in and redirected to `/`.
- **Given** an email that already exists (case-insensitive), **when** they sign up, **then** the form shows an error and no user is created.
- **Given** a registered user, **when** they log in at `/accounts/login/` with email and password, **then** they're authenticated. A bad password shows a generic error.
- **Given** a logged-in user, **when** they POST `/accounts/logout/`, **then** they're logged out. GET returns 405.
- Signup and login follow the `Signup` artboard in [design.md](../design.md). The header follows its Header component.
- Every page shows "Log in / Sign up", or "<first name> · Log out" (the logout is a POST form), in the header of `base.html`.
- `createsuperuser` works by email.

## Tests to write first
`apps/accounts/tests/test_models.py` → `UserModelTests`
- `test_email_is_username_field`: `User.USERNAME_FIELD == "email"`.
- `test_email_unique_case_insensitive`: creating `A@x.com` after `a@x.com` raises `IntegrityError` or a validation error. Normalize to lowercase on save.
- `test_create_superuser_by_email`.

`apps/accounts/tests/test_views.py` → `SignupViewTests`, `LoginLogoutTests`
- `test_signup_creates_and_logs_in`: 302 to `/`, and `_auth_user_id` is in the session.
- `test_signup_duplicate_email_rejected`: 200 with the form error; user count is unchanged.
- `test_signup_password_mismatch_rejected`.
- `test_login_with_email`.
- `test_login_wrong_password_generic_error`: the response doesn't reveal whether the email exists.
- `test_logout_requires_post`: GET → 405, POST → 302 and logged out.
- `test_pages_send_csp_header`: signup and login responses include `Content-Security-Policy`.
- `test_header_shows_login_links_when_anonymous`, `test_header_shows_name_when_authenticated`.

## Implementation notes
- New app `apps/accounts`:
  - `User(AbstractUser)` with `email = EmailField(unique=True)`, `USERNAME_FIELD = "email"`, `REQUIRED_FIELDS = []`, and a custom `UserManager` (create_user/create_superuser by email).
  - Keep `username` nullable and blank, or remove it (`username = None`). Pick one and note why in the PR.
- Settings: `AUTH_USER_MODEL = "accounts.User"`, plus `LOGIN_URL`, `LOGIN_REDIRECT_URL = "/"`, `LOGOUT_REDIRECT_URL = "/"`.
- Regenerate `mongo_migrations/admin/` and `mongo_migrations/auth/` against the new user model if needed. Check that `makemigrations --check` is clean.
- Views:
  - Signup is a `FormView` using a `UserCreationForm` subclass bound to the custom model, then `login()`.
  - Login and logout use `django.contrib.auth.views.LoginView`/`LogoutView`; Django's `LogoutView` is POST-only.
  - Templates go in `templates/accounts/`.
- Register `User` in the admin with a `UserAdmin` subclass whose `ordering`, `list_display` and fieldsets use `email`.
- **⚠ confirm: database reset.** Ask a human before doing either of these:
  - Locally: `docker compose down --volumes`, then `migrate`.
  - Production: drop the `entr_community` database on Atlas. This must happen **before** this PR merges, or the deploy's migrate step fails. A human runs it from their machine.
- Update CLAUDE.md:
  - The custom user model.
  - Accounts URLs.
  - The reset note.

## Out of scope
- Password reset and email verification (non-goal).
- Social login.
- Rate limiting (known risk, product.md).

## Manual verification
Sign up in the browser, log out, log back in, and open `/admin/` with a superuser created by email.
