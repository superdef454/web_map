#!/bin/sh
python manage.py migrate
python manage.py collectstatic --no-input
# python manage.py runserver 0.0.0.0:8000  # для разработки
gunicorn TransportMap.wsgi:application --bind 0.0.0.0:8000 --reload