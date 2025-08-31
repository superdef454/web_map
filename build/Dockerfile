FROM python:3.12-slim

# Предотвращение создания кэш-файлов Python и настройка окружения
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ="Europe/Moscow" \
    PIP_NO_CACHE_DIR=1

# Установка необходимых пакетов
RUN apt-get update && apt-get install -y --no-install-recommends \
    sudo \
    make \
    nginx \
    binutils \
    libproj-dev \
    gdal-bin \
    python3-gdal \
    supervisor \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Настройка Nginx
COPY ./build/nginx/nginx.conf /etc/nginx/conf.d/default.conf

# Настройка Supervisor
COPY ./build/supervisor/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Настройка рабочей директории
WORKDIR /app

# Установка зависимостей - этот слой кэшируется если requirements не меняется
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода приложения
COPY . /app

# Сборка статических файлов
RUN python manage.py collectstatic --noinput

# Порты
EXPOSE 8002 8080

# Использование supervisor для управления процессами
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
