FROM nginx:1.25

ENV APP_HOME=/home/
RUN mkdir $APP_HOME/static
WORKDIR $APP_HOME

RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d