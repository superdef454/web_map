FROM nginx:1.25

ENV HOME=/home/
ENV APP_HOME=/home/TransportMap
RUN mkdir $APP_HOME
RUN mkdir $APP_HOME/static
WORKDIR $APP_HOME

RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d