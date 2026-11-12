"""
Settings shared by every environment.

All values come from environment variables (see .env.example at the repo root).
local.py and production.py import everything from here and override what differs.
"""

from datetime import timedelta
from pathlib import Path

import environ
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()

# --- Core ----------------------------------------------------------------------

PORTAL_NAME = env("PORTAL_NAME", default="PORTAL_NAME")
SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

INTEGRATIONS_MODE = env("INTEGRATIONS_MODE", default="mock")
if INTEGRATIONS_MODE not in ("mock", "live"):
    raise ValueError(f"INTEGRATIONS_MODE must be 'mock' or 'live', got {INTEGRATIONS_MODE!r}")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",
    # Third party
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "storages",
    # Our apps (one per domain, see CLAUDE.md §4)
    "apps.core",
    "apps.accounts",
    "apps.brokers",
    "apps.listings",
    "apps.locations",
    "apps.leads",
    "apps.wallet",
    "apps.payments",
    "apps.invoicing",
    "apps.seo",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --- Database & cache ----------------------------------------------------------

# "postgis://..." selects the GeoDjango PostGIS backend.
DATABASES = {"default": env.db("DATABASE_URL")}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REDIS_URL = env("REDIS_URL")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

# --- Auth ----------------------------------------------------------------------

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Phone OTP login (see apps/accounts/services.py).
OTP_TTL_SECONDS = env.int("OTP_TTL_SECONDS", default=300)
OTP_MAX_ATTEMPTS = env.int("OTP_MAX_ATTEMPTS", default=5)
OTP_RESEND_SECONDS = env.int("OTP_RESEND_SECONDS", default=60)
OTP_MAX_PER_HOUR = env.int("OTP_MAX_PER_HOUR", default=5)

# Nafath identity verification for advertisers (see integrations/nafath/).
# Only used when INTEGRATIONS_MODE=live; the live client is not written yet.
NAFATH_BASE_URL = env("NAFATH_BASE_URL", default="")
NAFATH_APP_ID = env("NAFATH_APP_ID", default="")
NAFATH_APP_KEY = env("NAFATH_APP_KEY", default="")

# Listings (see apps/listings/services.py).
LISTING_POST_DAYS = env.int("LISTING_POST_DAYS", default=30)
LISTING_PHOTO_MAX_MB = env.int("LISTING_PHOTO_MAX_MB", default=10)
LISTING_PHOTO_MAX_COUNT = env.int("LISTING_PHOTO_MAX_COUNT", default=30)
# REGA platform API. Only used when INTEGRATIONS_MODE=live; the live client is not written yet.
REGA_BASE_URL = env("REGA_BASE_URL", default="")
REGA_API_KEY = env("REGA_API_KEY", default="")

# Leads (see apps/leads/services.py). SITE_URL is the public website, used in WhatsApp messages.
SITE_URL = env("SITE_URL", default="http://localhost:3000").rstrip("/")
# Secret mixed into the visitor fingerprint used to de-duplicate repeat clicks (no raw IPs stored).
LEAD_HASH_SALT = env("LEAD_HASH_SALT", default="local-dev-lead-salt")
# WhatsApp Cloud API, used to tell brokers about new leads. Only used when INTEGRATIONS_MODE=live.
WHATSAPP_PHONE_NUMBER_ID = env("WHATSAPP_PHONE_NUMBER_ID", default="")
WHATSAPP_ACCESS_TOKEN = env("WHATSAPP_ACCESS_TOKEN", default="")
WHATSAPP_LEAD_TEMPLATE = env("WHATSAPP_LEAD_TEMPLATE", default="new_lead")
WHATSAPP_EXPIRY_TEMPLATE = env("WHATSAPP_EXPIRY_TEMPLATE", default="listing_expiring")
# Advertisers are warned on WhatsApp this many days before a listing comes down.
LISTING_EXPIRY_WARNING_DAYS = env.int("LISTING_EXPIRY_WARNING_DAYS", default=3)

# Credit top-ups (see apps/payments/). The public address of this API, used for the mock
# checkout page that the browser opens in INTEGRATIONS_MODE=mock.
API_PUBLIC_URL = env("API_PUBLIC_URL", default="http://localhost:8000").rstrip("/")
# Moyasar. Only used when INTEGRATIONS_MODE=live, except the webhook secret (checked in both).
MOYASAR_SECRET_KEY = env("MOYASAR_SECRET_KEY", default="")
MOYASAR_WEBHOOK_SECRET = env("MOYASAR_WEBHOOK_SECRET", default="local-dev-webhook-secret")
# Unpaid checkouts are marked expired after this many minutes.
PAYMENT_PENDING_TTL_MINUTES = env.int("PAYMENT_PENDING_TTL_MINUTES", default=60)

# ZATCA e-invoices (see apps/invoicing/). Seller details printed on every invoice.
SELLER_NAME_AR = env("SELLER_NAME_AR", default="PORTAL_NAME")
SELLER_NAME_EN = env("SELLER_NAME_EN", default="PORTAL_NAME")
SELLER_VAT_NUMBER = env("SELLER_VAT_NUMBER", default="300000000000003")
SELLER_CR_NUMBER = env("SELLER_CR_NUMBER", default="")
SELLER_ADDRESS = env("SELLER_ADDRESS", default="Dammam, Saudi Arabia")
# VAT rate in basis points: 1500 = 15%. Package prices include VAT.
VAT_RATE_BP = env.int("VAT_RATE_BP", default=1500)

# JWTs travel in httpOnly cookies (see apps/accounts/cookies.py).
AUTH_COOKIE_ACCESS = "access_token"
AUTH_COOKIE_REFRESH = "refresh_token"
AUTH_COOKIE_SECURE = env.bool("AUTH_COOKIE_SECURE", default=False)
AUTH_COOKIE_DOMAIN = env("AUTH_COOKIE_DOMAIN", default="") or None

# --- Language & time -----------------------------------------------------------

LANGUAGE_CODE = "ar"
LANGUAGES = [("ar", "العربية"), ("en", "English")]
USE_I18N = True

# Times are stored in UTC and shown to users in Asia/Riyadh.
TIME_ZONE = "UTC"
USE_TZ = True
DISPLAY_TIME_ZONE = "Asia/Riyadh"

# --- Files ---------------------------------------------------------------------

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Uploads go to S3-compatible storage: MinIO locally, OCI Object Storage in production.
S3_PUBLIC_URL = env("S3_PUBLIC_URL")
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "endpoint_url": env("S3_ENDPOINT_URL"),
            "access_key": env("S3_ACCESS_KEY"),
            "secret_key": env("S3_SECRET_KEY"),
            "bucket_name": env("S3_BUCKET"),
            "region_name": env("S3_REGION"),
            "custom_domain": S3_PUBLIC_URL.split("://", 1)[-1],
            "url_protocol": S3_PUBLIC_URL.split("://", 1)[0] + ":",
            "querystring_auth": False,
            "file_overwrite": False,
        },
    },
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Browsers upload listing photos straight to storage with presigned URLs, so those URLs
# must use an address the browser can reach (the API container uses S3_ENDPOINT_URL).
S3_PUBLIC_ENDPOINT_URL = env("S3_PUBLIC_ENDPOINT_URL", default=env("S3_ENDPOINT_URL"))

IMGPROXY_URL = env("IMGPROXY_URL")
IMGPROXY_KEY = env("IMGPROXY_KEY")
IMGPROXY_SALT = env("IMGPROXY_SALT")

# --- Email ---------------------------------------------------------------------

vars().update(env.email_url("EMAIL_URL", default="consolemail://"))
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@localhost")

# --- API (Django REST Framework) -----------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.accounts.authentication.CookieJWTAuthentication",
    ],
    # Deny by default: every endpoint must opt in to public access explicitly.
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    # Per-IP limits for views that set a throttle_scope (per-phone limits are in services).
    "DEFAULT_THROTTLE_RATES": {
        "otp_request": "10/hour",
        "otp_verify": "30/hour",
        "auth_session": "120/hour",
        "nafath_start": "10/hour",
        "nafath_status": "300/hour",
        "lead_create": "30/hour",
        "topup_start": "30/hour",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
}

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = True

# --- Celery --------------------------------------------------------------------

CELERY_BROKER_URL = env("CELERY_BROKER_URL")
CELERY_TIMEZONE = "UTC"
CELERY_TASK_ACKS_LATE = True
# Scheduled jobs (nightly licence expiry etc.) are added here as features land.
CELERY_BEAT_SCHEDULE = {
    # 22:30 UTC = 01:30 Riyadh: re-check every live licence with REGA (renewed, cancelled…),
    # just before the expiry job so it works on fresh dates.
    "resync-rega-licences-nightly": {
        "task": "apps.listings.tasks.resync_active_licences",
        "schedule": crontab(hour=22, minute=30),
    },
    # 05:00 UTC = 08:00 Riyadh: WhatsApp advertisers whose listing comes down within 3 days.
    "warn-expiring-listings-daily": {
        "task": "apps.listings.tasks.warn_expiring_listings",
        "schedule": crontab(hour=5, minute=0),
    },
    # 23:00 UTC = 02:00 Riyadh: hide listings whose REGA licence or post period has ended.
    "expire-listings-nightly": {
        "task": "apps.listings.tasks.expire_listings",
        "schedule": crontab(hour=23, minute=0),
    },
    # Every 15 minutes: settle or expire top-ups the buyer abandoned at the checkout page.
    "expire-stale-payments": {
        "task": "apps.payments.tasks.expire_stale_payments",
        "schedule": crontab(minute="*/15"),
    },
}

# --- Logging -------------------------------------------------------------------
# Never log national IDs, phone numbers or OTP codes in plain text (PDPL).

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    # WeasyPrint's font tools print hundreds of lines per invoice PDF at INFO.
    "loggers": {
        "fontTools": {"level": "WARNING"},
        "weasyprint": {"level": "WARNING"},
    },
}
