from pathlib import Path
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY', default='django-insecure-CHANGE-ME-in-production')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = [h.strip() for h in config('ALLOWED_HOSTS', default='*').split(',') if h.strip()]

# Django 4+ inahitaji hii kwa POST/login kupitia HTTPS.
# BILA HII, kuingia kwenye dashboard production kutashindwa kwa CSRF error.
# Mfano: CSRF_TRUSTED_ORIGINS=https://kilimoni.onrender.com
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in config('CSRF_TRUSTED_ORIGINS', default='').split(',') if o.strip()
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'bot',
    'crops',
    'analytics',
    'whatsapp',
    'admin_panel',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'mkulima_ai.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'mkulima_ai.wsgi.application'

# Database - Supabase kwa production, SQLite kwa local dev
if config('DB_USER', default=''):
    DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': config('DB_NAME', default='postgres'),
                'USER': config('DB_USER'),
                'PASSWORD': config('DB_PASSWORD', default=''),
                'HOST': config('DB_HOST', default=''),
                'PORT': config('DB_PORT', default='5432'),
                'CONN_MAX_AGE': config('DB_CONN_MAX_AGE', default=0, cast=int),
            }
        }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }






AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'sw'
TIME_ZONE = 'Africa/Dar_es_Salaam'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── Usalama (production tu) ──────────────────
if not DEBUG:
    # Render iko nyuma ya proxy — bila hii Django hajui request ni HTTPS
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    # Render tayari inalazimisha HTTPS. Washa hizi ukitaka ugumu zaidi:
    SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=False, cast=bool)
    SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=0, cast=int)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = bool(SECURE_HSTS_SECONDS)
    SECURE_HSTS_PRELOAD = bool(SECURE_HSTS_SECONDS)

# ── Logging — muhimu kwa ku-debug webhook kwenye Render Logs ──
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {'format': '[{levelname}] {asctime} {name}: {message}', 'style': '{'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'simple'},
    },
    'root': {'handlers': ['console'], 'level': 'WARNING'},
    'loggers': {
        'bot': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'whatsapp': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'admin_panel': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

CORS_ALLOWED_ORIGINS = config('CORS_ORIGINS', default='http://localhost:3000').split(',')
CORS_ALLOW_ALL_ORIGINS = DEBUG

# WhatsApp
WHATSAPP_API_TOKEN = config('WHATSAPP_API_TOKEN', default='')
WHATSAPP_PHONE_NUMBER_ID = config('WHATSAPP_PHONE_NUMBER_ID', default='')
WHATSAPP_VERIFY_TOKEN = config('WHATSAPP_VERIFY_TOKEN', default='')
WHATSAPP_BUSINESS_ACCOUNT_ID = config('WHATSAPP_BUSINESS_ACCOUNT_ID', default='')
# Meta huondoa Graph API versions za zamani baada ya ~miaka 2.
# Angalia version mpya kwenye Meta App Dashboard, kisha weka hapa kwa env var.
WHATSAPP_API_VERSION = config('WHATSAPP_API_VERSION', default='v21.0')
WHATSAPP_API_URL = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"

# Login URL
LOGIN_URL = '/dashboard/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/dashboard/login/'

# Claude AI
ANTHROPIC_API_KEY = config('ANTHROPIC_API_KEY', default='')
CLAUDE_MODEL = 'claude-sonnet-4-6'

# Green API (testing tu)
GREENAPI_URL = config('GREENAPI_URL', default='')
GREENAPI_INSTANCE_ID = config('GREENAPI_INSTANCE_ID', default='')
GREENAPI_TOKEN = config('GREENAPI_TOKEN', default='')

# Groq AI (fallback yenye akili)
GROQ_API_KEY = config('GROQ_API_KEY', default='')
GROQ_MODEL = config('GROQ_MODEL', default='llama-3.3-70b-versatile')