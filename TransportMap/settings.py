import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


SECRET_KEY = os.environ.get("SECRET_KEY", "foo")
DEBUG = bool(os.environ.get("DEBUG", default=1))
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "0.0.0.0 127.0.0.1 localhost").split(" ") + ["optimove"]
CSRF_TRUSTED_ORIGINS = ["http://localhost:1337", "http://127.0.0.1:1337", "http://0.0.0.0:1337", "http://127.0.0.1:82"]

if os.name == 'nt':
    GDAL_LIBRARY_PATH = os.getenv('GDAL_LIBRARY_PATH', r'C:\OSGeo4W\bin\gdal310.dll')
    GEOS_LIBRARY_PATH = os.getenv('GEOS_LIBRARY_PATH', r'C:\OSGeo4W\bin\geos_c.dll')

DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000

INSTALLED_APPS = [
    'fontawesomefree',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.gis',
    # Django REST Framework
    'rest_framework',
    'rest_framework_gis',
    'django_filters',
    'drf_spectacular',
    # Local apps
    'PetriNET',
    'accounts'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.gzip.GZipMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'TransportMap.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'TransportMap', 'templates')
        ],
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

WSGI_APPLICATION = 'TransportMap.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': os.environ.get("SQL_ENGINE", "django.contrib.gis.db.backends.postgis"),
        'NAME': os.getenv('POSTGRES_DB', 'OptiMoVe'),
        'USER': os.getenv('POSTGRES_USER', 'postgres'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD', 'postgres'),
        'HOST': os.getenv('POSTGRES_HOST', 'localhost'),
        'PORT': os.getenv('POSTGRES_PORT', '5432'),
        'TEST': {
            'NAME': 'test_optimove',
        },
    },
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'log/PetriNET.log',
            'formatter': 'verbose',
        },
    },
    'formatters': {
        'simple': {
            'format': '%(asctime)s %(levelname)s %(message)s',
        },
        'verbose': {
            'format': '%(asctime)s %(levelname)s [%(name)s:%(lineno)s] %(message)s',
        },
    },
    'loggers': {
        '': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
# LOGGING = {
#     'version': 1,
#     'filters': {
#         'require_debug_true': {
#             '()': 'django.utils.log.RequireDebugTrue',
#         }
#     },
#     'handlers': {
#         'console': {
#             'level': 'DEBUG',
#             'filters': ['require_debug_true'],
#             'class': 'logging.StreamHandler',
#         }
#     },
#     'loggers': {
#         'django.db.backends': {
#             'level': 'DEBUG',
#             'handlers': ['console'],
#         }
#     }
# }

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

LANGUAGE_CODE = 'ru-RU'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
STATIC_URL = '/static/'
STATICFILES_DIRS = (
    os.path.join(BASE_DIR, 'TransportMap', 'static'),
)
STATIC_ROOT = os.path.join(BASE_DIR, 'static')
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Django REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'TransportMap.utils.ValidatedPageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'TransportMap.utils.ValidatedDjangoFilterBackend',
        'TransportMap.utils.ValidatedSearchFilter',
        'TransportMap.utils.ValidatedOrderingFilter',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'EXCEPTION_HANDLER': 'TransportMap.error_handlers.custom_exception_handler',  # Кастомный обработчик ошибок
}

# drf-spectacular settings
SPECTACULAR_SETTINGS = {
    'TITLE': 'TransportMap API',
    'DESCRIPTION': 'API для работы с транспортными картами и расчётом нагрузки',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SCHEMA_PATH_PREFIX': r'/api/',
    'DEFAULT_GENERATOR_CLASS': 'drf_spectacular.generators.SchemaGenerator',
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
        'displayOperationId': False,
        'defaultModelsExpandDepth': 3,
        'defaultModelExpandDepth': 3,
        'displayRequestDuration': True,
        'docExpansion': 'list',
        'supportedSubmitMethods': ['get', 'put', 'post', 'delete', 'patch'],
        'showExtensions': True,
        'showCommonExtensions': True,
        # 'tryItOutEnabled': True,
    },
    'REDOC_UI_SETTINGS': {
        'hideDownloadButton': False,
        'theme': {
            'colors': {
                'primary': {'main': '#1976d2'},
            }
        }
    },
}
