import os
from pathlib import Path

import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR, "ai/.env"))

SECRET_KEY = env("DJANGO_SECRET")
DEBUG = env("DEBUG").lower() == "true"
STAGE = env("STAGE").lower() == "true"


# HOSTS
ALLOWED_HOSTS = ['api.jobescape.me', 'api.jobescape.us', 'localhost']
if STAGE:
    ALLOWED_HOSTS = [
        'stage.api.jobescape.me',
        'stage.api.jobescape.us',
        'academy-stage-397596874269.us-east1.run.app'
    ]
if DEBUG:
    ALLOWED_HOSTS.extend([
        '.localhost',
        '127.0.0.1',
        '[::1]',
        '0.0.0.0',
        # env("NGROK_HOST", str)
    ])
    # NGROK_IP = env("NGROK_IP", str)
    # CSRF_TRUSTED_ORIGINS = [NGROK_IP]


# CORS
CORS_ALLOWED_ORIGINS = [
    "https://jobescape.me",  # new funnel
    "https://api.jobescape.me",  # backend
    "https://app.jobescape.me",  # new app
    "https://jobescape.us",  # new app
    "https://app.jobescape.us",
    "https://analytics.jobescape.me",
]
if STAGE:
    CORS_ALLOWED_ORIGINS.extend([
        "https://stage.jobescape.me",  # stage app
        "https://funnels.jobescape.me",  # stage funnel
        "https://funnels.jobescape.us",  # stage funnel
    ])
if DEBUG:
    CORS_ALLOWED_ORIGINS.extend([
        "http://0.0.0.0:80",
        "http://172.31.19.3",
        "https://stage3.jobescape.me",
        # env("LOCAL_IP", str),
        # env("NGROK_IP", str)
    ]
    )
    CORS_ALLOWED_ORIGIN_REGEXES = [
        # r"^https:\/\/.+\.ngrok-free\.app$",
        r"^http:\/\/localhost(:[0-9]*)?$",
        r"^https:\/\/.+jobescape-team\.vercel\.app"
    ]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'main',
    'jlab',
    'rest_framework',
    'rest_framework_simplejwt',
]
if DEBUG:
    INSTALLED_APPS.append('silk')

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

if DEBUG:
    MIDDLEWARE.append('silk.middleware.SilkyMiddleware')

ROOT_URLCONF = 'academy.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'academy.wsgi.application'


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env("PRODUCTION_DB_NAME"),
        'USER': env("PRODUCTION_DB_USER"),
        'PASSWORD': env("PRODUCTION_DB_PASS"),
        'HOST': env("PRODUCTION_DB_HOST"),
        # 'PORT': env("PRODUCTION_DB_PORT"), # google cloud does not allow to enter empty SECRETS
        'DISABLE_SERVER_SIDE_CURSORS': True
    },
    # 'development': {
    #     'ENGINE': 'django.db.backends.postgresql',
    #     'NAME': env("DEVELOPMENT_DB_NAME"),
    #     'USER': env("DEVELOPMENT_DB_USER"),
    #     'PASSWORD': env("DEVELOPMENT_DB_PASS"),
    #     'HOST': env("DEVELOPMENT_DB_HOST"),
    #     'PORT': env("DEVELOPMENT_DB_PORT"),
    # },
    # 'remote': {
    #     'ENGINE': 'django.db.backends.postgresql',
    #     'NAME': env("REMOTE_DB_NAME"),
    #     'USER': env("REMOTE_DB_USER"),
    #     'PASSWORD': env("REMOTE_DB_PASS"),
    #     'HOST': env("REMOTE_DB_HOST"),
    #     # 'PORT': env("REMOTE_DB_PORT"), # google cloud does not require port
    #     # 'OPTIONS': {
    #     #    'sslmode': 'require',
    #     # }
    # }
}
DATABASES["default"].update(DATABASES[env("DATABASE_SELECTOR")])

# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_AUTHENTICATION_CLASSES': ('custom.custom_backend.PrefetchedJWTAuthentication',),
}

SIMPLE_JWT = {
    'SIGNING_KEY': env("JWT_SIGNING_KEY"),
    'ALGORITHM': env("JWT_ALGORITHM"),
}

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static/')


DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000
