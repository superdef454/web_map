from TransportMap.settings import *

# Дальше в этом файле будут переопределяться настройки проекта под вашу систему

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'OptiMoVe',
        'USER': 'postgres',
        'PASSWORD': 'postgres',
        'HOST': 'localhost',
        'TEST': {
            'NAME': 'test_optimove',  # К примеру в настройках переопределим таблицу для проведения тестирования, чтобы не трогать основную БД (её предварительно нужно создать)
        },
    }
}
