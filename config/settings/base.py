"""
Base settings for Manji project.
"""

import os
from datetime import timedelta
from pathlib import Path

import environ

# Prefer IPv4 for outbound HTTP (this host has broken IPv6 routing, which
# otherwise makes requests hang or fail with "Network is unreachable").
try:
    import urllib3.util.connection as _url3_conn

    _url3_conn.HAS_IPV6 = False
except Exception:
    pass

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load environment variables from .env file
env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
]

LOCAL_APPS = [
    "apps.core",
    "apps.users",
    "apps.stories",
    "apps.chapters",
    "apps.projects",
    "apps.characters",
    "apps.ai",
    "apps.scenes",
    "apps.assets",
    "apps.storyboard",
    "apps.animation",
    "apps.audio",
    "apps.tour",
    "apps.official",
    "apps.library",
    "apps.social",
    "apps.notifications",
    "apps.moderation",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ---------------------------------------------------------------------------
# Security Middleware (CSP, etc.)
# ---------------------------------------------------------------------------
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_EMBEDDER_POLICY = "require-corp"

# CSP settings (used by csp middleware)
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'",)
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")
CSP_IMG_SRC = ("'self'", "data:", "https:")
CSP_FONT_SRC = ("'self'", "data:")
CSP_CONNECT_SRC = ("'self'", "wss:", "https:")
CSP_FRAME_ANCESTORS = ("'none'",)
CSP_FORM_ACTION = ("'self'",)
CSP_BASE_URI = ("'self'",)
CSP_OBJECT_SRC = ("'none'",)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "csp.middleware.CSPMiddleware",
]

# ---------------------------------------------------------------------------
# URL / WSGI / ASGI
# ---------------------------------------------------------------------------
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DATABASES = {
    "default": env.db("DATABASE_URL", default="sqlite:///db.sqlite3")
}
DATABASES["default"]["ATOMIC_REQUESTS"] = True

# ---------------------------------------------------------------------------
# Custom User Model
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "users.User"

# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static & Media files
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": "apps.core.exceptions.custom_exception_handler",
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardResultsSetPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/day",
        "user": "1000/day",
    },
}

# ---------------------------------------------------------------------------
# Simple JWT
# ---------------------------------------------------------------------------
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
        "http://localhost:5176",
        "http://127.0.0.1:5176",
    ],
)
CORS_ALLOW_CREDENTIALS = True

# ---------------------------------------------------------------------------
# drf-spectacular (OpenAPI)
# ---------------------------------------------------------------------------
SPECTACULAR_SETTINGS = {
    "TITLE": "Manji API",
    "DESCRIPTION": "Where Stories Come to Life – REST API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# ---------------------------------------------------------------------------
# Email (override in dev/prod)
# ---------------------------------------------------------------------------
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@manji.io")

# ---------------------------------------------------------------------------
# Gmail API (OAuth2) for transactional emails
# ---------------------------------------------------------------------------
# Get these from Google Cloud Console:
# 1. Create OAuth 2.0 Client ID (Web application)
# 2. Authorized redirect URI: https://developers.google.com/oauthplayground
# 3. Use OAuth Playground to get refresh token with scope:
#    https://www.googleapis.com/auth/gmail.send
GOOGLE_OAUTH_CLIENT_ID = env("GOOGLE_OAUTH_CLIENT_ID", default="")
GOOGLE_OAUTH_CLIENT_SECRET = env("GOOGLE_OAUTH_CLIENT_SECRET", default="")
GOOGLE_OAUTH_REFRESH_TOKEN = env("GOOGLE_OAUTH_REFRESH_TOKEN", default="")

# ---------------------------------------------------------------------------
# Frontend URL for email links
# ---------------------------------------------------------------------------
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:5173")

# ---------------------------------------------------------------------------
# File upload limits
# ---------------------------------------------------------------------------
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024   # 20 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024   # 20 MB

# Largest single asset a creator may upload to the project library (MB).
ASSET_MAX_UPLOAD_MB = env.int("ASSET_MAX_UPLOAD_MB", default=100)

# Largest single voice/audio clip a creator may upload to the voice studio (MB).
AUDIO_MAX_UPLOAD_MB = env.int("AUDIO_MAX_UPLOAD_MB", default=50)

# ---------------------------------------------------------------------------
# AI integrations (image generation + idea generation)
# ---------------------------------------------------------------------------
# Image provider to use by default when none is given by the client.
# Supported values: "dalle", "stability", "leonardo", "local".
AI_IMAGE_PROVIDER_DEFAULT = env("AI_IMAGE_PROVIDER_DEFAULT", default="dalle")

# Provider API keys (empty keys disable that provider)
AI_OPENAI_API_KEY = env("AI_OPENAI_API_KEY", default="")
AI_OPENAI_IMAGE_MODEL = env("AI_OPENAI_IMAGE_MODEL", default="dall-e-3")
AI_STABILITY_API_KEY = env("AI_STABILITY_API_KEY", default="")
AI_LEONARDO_API_KEY = env("AI_LEONARDO_API_KEY", default="")

# Text/idea generation – any OpenAI-compatible chat-completions endpoint
# (OpenAI, OpenRouter, Together, local Ollama/llama.cpp, etc.)
AI_TEXT_API_KEY = env("AI_TEXT_API_KEY", default="")
AI_TEXT_BASE_URL = env("AI_TEXT_BASE_URL", default="https://api.openai.com/v1")
AI_TEXT_MODEL = env("AI_TEXT_MODEL", default="gpt-4o-mini")

# Development fallback: renders a real local image (gradient placeholder) with
# Pillow when no image provider is configured. Disabled in production.
AI_ALLOW_LOCAL_PLACEHOLDER = env.bool("AI_ALLOW_LOCAL_PLACEHOLDER", default=DEBUG)

# Per-user daily quotas (counted per calendar day)
AI_IMAGE_QUOTA_DAILY = env.int("AI_IMAGE_QUOTA_DAILY", default=20)
AI_TEXT_QUOTA_DAILY = env.int("AI_TEXT_QUOTA_DAILY", default=30)

# Manji AI chat (Phase 1) – built on the same OpenAI-compatible text endpoint
AI_CHAT_PROVIDER = env("AI_CHAT_PROVIDER", default="openai")
AI_CHAT_MODEL = env("AI_CHAT_MODEL", default="")  # falls back to AI_TEXT_MODEL
AI_CHAT_MAX_TOKENS = env.int("AI_CHAT_MAX_TOKENS", default=800)
# How many previous turns to include as context for the model.
AI_CHAT_HISTORY_MESSAGES = env.int("AI_CHAT_HISTORY_MESSAGES", default=12)
# Max characters of the current draft/chapter sent to the model.
AI_CHAT_CONTEXT_MAX_CHARS = env.int("AI_CHAT_CONTEXT_MAX_CHARS", default=8000)

# Manji AI chat providers (Phase 4). Keys are optional: leave empty to disable
# a provider. AI_CHAT_FALLBACK_PROVIDER names a second provider that is tried
# automatically when the primary raises an error.
GEMINI_API_KEY = env("GEMINI_API_KEY", default="")
AI_GEMINI_MODEL = env("AI_GEMINI_MODEL", default="gemini-1.5-flash")
OPENROUTER_API_KEY = env("OPENROUTER_API_KEY", default="")
AI_OPENROUTER_MODEL = env("AI_OPENROUTER_MODEL", default="")
AI_CHAT_FALLBACK_PROVIDER = env("AI_CHAT_FALLBACK_PROVIDER", default="")
