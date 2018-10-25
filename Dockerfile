# Frappe Bench
FROM alpine:latest
MAINTAINER developers@frappe.io

USER root
ENV LANG C.UTF-8

COPY docker-entrypoint.sh usr/local/bin/docker-entrypoint.sh
RUN ln -s usr/local/bin/docker-entrypoint.sh / # backwards compat

RUN apk add --update --no-cache \
  build-base \
  libffi-dev \
  git \
  su-exec \
  nodejs \
  yarn \
  python-dev \
  py-pip \
  jpeg-dev \
  zlib-dev \
  libxslt-dev \
  libxml2-dev \
  postgresql-dev \
  gcc \
  python3-dev \
  musl-dev \
  mysql-client

RUN pip install --upgrade setuptools pip && rm -rf ~/.cache/pip
RUN mkdir -p /home/frappe && adduser -h /home/frappe -D frappe

ENV DOCKERIZE_VERSION v0.6.1
RUN wget https://github.com/jwilder/dockerize/releases/download/$DOCKERIZE_VERSION/dockerize-linux-amd64-$DOCKERIZE_VERSION.tar.gz \
    && tar -C /usr/local/bin -xzvf dockerize-linux-amd64-$DOCKERIZE_VERSION.tar.gz \
    && rm dockerize-linux-amd64-$DOCKERIZE_VERSION.tar.gz

RUN cd /tmp \
  && wget -c https://github.com/frappe/wkhtmltopdf/raw/master/wkhtmltox-0.12.3_linux-generic-amd64.tar.xz \
  && tar xvf wkhtmltox-0.12.3_linux-generic-amd64.tar.xz \
  && cp wkhtmltox/bin/wkhtmltopdf /usr/local/bin/wkhtmltopdf \
  && chmod o+x /usr/local/bin/wkhtmltopdf

RUN git clone https://github.com/frappe/bench.git /home/frappe/.bench -b master \
  && pip install -e /home/frappe/.bench \
  && chown -R frappe:frappe /home/frappe

USER frappe
RUN cd /home/frappe \
  && bench init frappe-bench --in-docker \
  && cd frappe-bench

WORKDIR /home/frappe/frappe-bench

VOLUME /home/frappe/frappe-bench/sites

EXPOSE 8000
EXPOSE 9000
EXPOSE 6787

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["start"]
