"""
Django settings for vogon project.

Generated by 'django-admin startproject' using Django 1.8.1.

For more information on this file, see
https://docs.djangoproject.com/en/1.8/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.8/ref/settings/
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os, sys, requests
from urlparse import urlparse
import socket
import dj_database_url
import djcelery
from datetime import timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.8/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'secretsecret')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = eval(os.environ.get('DEBUG', 'False'))

ALLOWED_HOSTS = ['*']

# Application definition

INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'concepts',
    'annotations',
    'rest_framework',
    'corsheaders',
    'djcelery',
    'repository',
    'social.apps.django_app.default',
)

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.security.SecurityMiddleware',
)

ROOT_URLCONF = 'vogon.urls'

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
                'annotations.context_processors.google',
                'annotations.context_processors.version',
                'annotations.context_processors.base_url',
            ],
        },
    },
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    'PAGE_SIZE': 50,

}

WSGI_APPLICATION = 'vogon.wsgi.application'

# Database
# https://docs.djangoproject.com/en/1.8/ref/settings/#databases


DATABASES = {
    'default': dj_database_url.config()
}
DATABASES['default']['ENGINE'] = 'django.db.backends.postgresql_psycopg2'


AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend', # default
    'social.backends.github.GithubOAuth2',
)
ANONYMOUS_USER_ID = -1
BASE_URL = os.environ.get('BASE_URL', '/')
SOCIAL_AUTH_GITHUB_KEY = os.environ.get('SOCIAL_AUTH_GITHUB_KEY', None)
SOCIAL_AUTH_GITHUB_SECRET = os.environ.get('SOCIAL_AUTH_GITHUB_SECRET', None)
SOCIAL_AUTH_LOGIN_REDIRECT_URL = BASE_URL
SOCIAL_AUTH_GITHUB_SCOPE = ['user']



# Internationalization
# https://docs.djangoproject.com/en/1.8/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.8/howto/static-files/


CORS_ORIGIN_ALLOW_ALL = False
CORS_ALLOW_CREDENTIALS = False

APPEND_SLASH = False
CRISPY_TEMPLATE_PACK = 'bootstrap3'


SUBPATH = '/'
# Honor the 'X-Forwarded-Proto' header for request.is_secure()
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Allow all host headers
ALLOWED_HOSTS = ['*']

# Static asset configuration
BASE_PATH = os.environ.get('BASE_PATH', '/')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
STATIC_ROOT = os.environ.get('STATIC_ROOT', os.path.join(PROJECT_ROOT, 'staticfiles'))
STATIC_URL = BASE_URL + 'static/'

STATICFILES_DIRS = (
    os.path.join(BASE_DIR, 'static'),
)

JARS_KEY = '050814a54ac5c81b990140c3c43278031d391676'
AUTH_USER_MODEL = 'annotations.VogonUser'


es = urlparse(os.environ.get('SEARCHBOX_URL') or 'http://127.0.0.1:9200/')
port = es.port or 80

# AWS Access Key and Secret Key credentials
AWS_ACCESS_KEY = os.environ.get('AWS_ACCESS_KEY', None)
AWS_SECRET_KEY = os.environ.get('AWS_SECRET_KEY', None)
S3_BUCKET = 'vogonweb-test'
DEFAULT_USER_IMAGE = 'https://s3-us-west-2.amazonaws.com/vogonweb-test/defaultprofile.png'


TEMPORAL_PREDICATES = {
    'start': 'http://www.digitalhps.org/concepts/CONbbbb0940-84be-4450-b92f-557a78249ebd',
    'end': 'http://www.digitalhps.org/concepts/CONbfd1fc2d-0393-4bdb-92f5-7500cdc507f8',
    'occur': 'http://www.digitalhps.org/concepts/ba626314-5d54-41b6-8f41-0013be5269be'
}

BROKER_POOL_LIMIT = 0

PREDICATES = {
    'have': 'http://www.digitalhps.org/concepts/CON83f5110b-5034-4c95-82f8-8f80ff55a1b9',
    'be': 'http://www.digitalhps.org/concepts/CON3fbc4870-6028-4255-9998-14acf028a316'
}


CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'default_cache_table',
    }
}

CONCEPTPOWER_USERID = os.environ.get('CONCEPTPOWER_USERID', None)
CONCEPTPOWER_PASSWORD = os.environ.get('CONCEPTPOWER_PASSWORD', None)
CONCEPTPOWER_ENDPOINT = os.environ.get('CONCEPTPOWER_ENDPOINT', 'http://chps.asu.edu/conceptpower/rest/')
CONCEPTPOWER_NAMESPACE = os.environ.get('CONCEPTPOWER_NAMESPACE', '{http://www.digitalhps.org/}')

QUADRIGA_USERID = os.environ.get('QUADRIGA_USERID', '')
QUADRIGA_PASSWORD = os.environ.get('QUADRIGA_PASSWORD', '')
QUADRIGA_ENDPOINT = os.environ.get('QUADRIGA_ENDPOINT', '')
QUADRIGA_CLIENTID = os.environ.get('QUADRIGA_CLIENTID', 'vogonweb')
QUADRIGA_PROJECT = os.environ.get('QUADRIGA_PROJECT', 'vogonweb')


BASE_URI_NAMESPACE = u'http://www.vogonweb.net'

# Celery config.

djcelery.setup_loader()
CELERYBEAT_SCHEDULE = {
    'accession_ready_relationsets': {
        'task': 'annotations.tasks.accession_ready_relationsets',
        'schedule': timedelta(seconds=30),
    },
}

CELERY_TIMEZONE = 'UTC'

GOOGLE_ANALYTICS_ID = os.environ.get('GOOGLE_ANALYTICS_ID', None)

VERSION = '0.4'


# Giles and HTTP.
GILES = os.environ.get('GILES', 'https://diging-dev.asu.edu/giles-review')
IMAGE_AFFIXES = ['png', 'jpg', 'jpeg', 'tiff', 'tif']
GET = requests.get
POST = requests.post
GILES_APP_TOKEN = os.environ.get('GILES_APP_TOKEN', 'nope')
GILES_DEFAULT_PROVIDER = os.environ.get('GILES_DEFAULT_PROVIDER', 'github')
MAX_GILES_UPLOADS = 20


GOAT = os.environ.get('GOAT', 'http://127.0.0.1:8000')
GOAT_APP_TOKEN = os.environ.get('GOAT_APP_TOKEN')

LOGIN_URL = BASE_URL + 'login/github/'
# LOGOUT_REDIRECT_URL = 'home'

LOGLEVEL = os.environ.get('LOGLEVEL', 'DEBUG')