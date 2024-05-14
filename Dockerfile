# Указывает Docker использовать официальный образ python 3 с dockerhub в качестве базового образа
FROM python:3.10.6

EXPOSE 8000
# Устанавливает переменную окружения, которая гарантирует, что вывод из python будет отправлен прямо в терминал без предварительной буферизации
ENV PYTHONUNBUFFERED 1
# Копирует все файлы из нашего локального проекта в контейнер
ADD ./ /web_map
# Устанавливает рабочий каталог контейнера
WORKDIR /web_map
# Запускает команду pip install для всех библиотек, перечисленных в req.txt
RUN pip install -r req.txt

COPY --chmod=555 entrypoint.sh /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
