# Frappe Framework for OSS Scanner. Enrolled at https://github.com/anthropics/oss-scanner/tree/main/projects/frappe;
# the scanner builds this file with the repository as its context, and reads threat_model.md in this directory.
# Adapted from frappe_docker (images/production/Containerfile), but built from the scanner's checkout instead of a
# GitHub clone: the checkout is the bench's apps/frappe, and /src is a symlink to it.
# MariaDB and Redis run inside this one container (the scanner has no compose services); start them with
# `frappe-services start`. A site, test_site, is created during the build.
FROM python:3.14-slim-trixie

ARG NODE_VERSION=24
ARG WKHTMLTOPDF_VERSION=0.12.6.1-3
ARG WKHTMLTOPDF_DISTRO=bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    NVM_DIR=/opt/nvm \
    NVM_SYMLINK_CURRENT=true \
    PATH=/opt/nvm/current/bin:/home/frappe/.local/bin:${PATH}

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl wget git sudo procps file media-types tzdata-legacy cron less jq \
      build-essential pkg-config \
      # database and cache
      mariadb-server mariadb-client libmariadb-dev redis-server \
      # python package build dependencies
      libffi-dev liblcms2-dev libldap2-dev libsasl2-dev libtiff-dev libwebp-dev libbz2-dev libpq-dev \
      # PDF rendering: Chromium (as frappe_docker installs it), weasyprint and wkhtmltopdf
      chromium-headless-shell libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0 libpangocairo-1.0-0 fonts-cantarell xfonts-75dpi xfonts-base \
    && arch="$(dpkg --print-architecture)" \
    && deb="wkhtmltox_${WKHTMLTOPDF_VERSION}.${WKHTMLTOPDF_DISTRO}_${arch}.deb" \
    && curl -fsSLO "https://github.com/wkhtmltopdf/packaging/releases/download/${WKHTMLTOPDF_VERSION}/${deb}" \
    && apt-get install -y --no-install-recommends "./${deb}" && rm "${deb}" \
    && rm -rf /var/lib/apt/lists/*

# Frappe needs utf8mb4 with this exact collation, or bench new-site refuses the server.
RUN printf '[mysqld]\ncharacter-set-client-handshake = FALSE\ncharacter-set-server = utf8mb4\ncollation-server = utf8mb4_unicode_ci\nbind-address = 127.0.0.1\n\n[mysql]\ndefault-character-set = utf8mb4\n' \
      > /etc/mysql/mariadb.conf.d/99-frappe.cnf

# Node and yarn, through nvm as frappe_docker does, somewhere both root and frappe can use them.
RUN mkdir -p "${NVM_DIR}" \
    && curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.6/install.sh | bash \
    && . "${NVM_DIR}/nvm.sh" \
    && nvm install "${NODE_VERSION}" && nvm alias default "${NODE_VERSION}" \
    && npm install -g yarn \
    && rm -rf "${NVM_DIR}/.cache" \
    && node --version && yarn --version

# The checkout belongs to frappe, but the scanner works in /src as root: let git read it anyway.
RUN useradd -m -s /bin/bash frappe \
    && echo "frappe ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/frappe \
    && git config --system --add safe.directory '*' \
    && pip install --no-cache-dir frappe-bench

# Starts and stops MariaDB and the two Redis servers the bench is configured for. Works offline.
RUN cat > /usr/local/bin/frappe-services <<'EOF' && chmod 755 /usr/local/bin/frappe-services
#!/bin/sh
set -e
case "${1:-start}" in
  start)
    mkdir -p /run/mysqld && chown mysql:mysql /run/mysqld
    if ! mariadb-admin -uroot -proot ping --silent 2>/dev/null; then
      (mariadbd-safe --user=mysql >/dev/null 2>&1 &)
      for _ in $(seq 60); do mariadb-admin ping --silent 2>/dev/null && break; sleep 1; done
    fi
    for port in 13000 11000; do
      redis-cli -p "$port" ping >/dev/null 2>&1 || redis-server --port "$port" --bind 127.0.0.1 --save '' --daemonize yes
    done ;;
  stop)
    mariadb-admin -uroot -proot shutdown 2>/dev/null || mariadb-admin shutdown || true
    for port in 13000 11000; do redis-cli -p "$port" shutdown nosave 2>/dev/null || true; done ;;
esac
EOF

# scanner contract: the checkout lives inside the image, at /src
COPY --chown=frappe:frappe . /src
WORKDIR /src

# Build a bench, then replace its frappe clone with the checkout itself and point /src back at it, so the code under
# test is the code that runs. The checkout must be a real directory inside the bench: Frappe finds the bench from its
# own real path. file:// makes git copy rather than hardlink, which fails on overlay filesystems.
USER frappe
RUN cd /home/frappe \
    && bench init --skip-assets --frappe-path file:///src --python "$(command -v python3)" frappe-bench \
    && cd frappe-bench \
    && rm -rf apps/frappe \
    && sudo mv /src apps/frappe && sudo ln -s /home/frappe/frappe-bench/apps/frappe /src \
    && env/bin/pip install --no-cache-dir -e apps/frappe \
    && bench setup requirements && bench setup requirements --dev \
    && bench build --app frappe \
    && bench set-config -g chromium_path /usr/lib/chromium/chromium-headless-shell

# Create test_site (Administrator password: admin; MariaDB root password: root), plus one user per actor level so a
# finding can be shown from the least-privileged actor (all use the password scanner-user-pw):
#   website@example.com  Website User
#   user@example.com     plain System User (only the Desk User role)
#   manager@example.com  System Manager, for the "they can already do this" test
USER root
RUN set -e \
    && mkdir -p /run/mysqld && chown mysql:mysql /run/mysqld \
    && (mariadbd-safe --user=mysql >/dev/null 2>&1 &) \
    && for _ in $(seq 60); do mariadb-admin ping --silent 2>/dev/null && break; sleep 1; done \
    && mariadb -e "ALTER USER 'root'@'localhost' IDENTIFIED BY 'root'; FLUSH PRIVILEGES;" \
    && frappe-services start \
    && su frappe -c "cd /home/frappe/frappe-bench \
         && bench new-site test_site --db-root-password root --admin-password admin --mariadb-user-host-login-scope=localhost \
         && bench --site test_site set-config host_name http://test_site:8000 \
         && bench --site test_site add-user website@example.com --first-name Website --password scanner-user-pw --user-type 'Website User' \
         && bench --site test_site add-user user@example.com --first-name Plain --password scanner-user-pw --user-type 'System User' --add-role 'Desk User' \
         && bench --site test_site add-user manager@example.com --first-name Manager --password scanner-user-pw --user-type 'System User' --add-role 'System Manager' \
         && bench use test_site" \
    && frappe-services stop

# Cheap check that the image works: the site answers over HTTP. A failure does not abort the build.
RUN frappe-services start \
    && (su frappe -c "cd /home/frappe/frappe-bench \
          && (bench serve --port 8000 > /tmp/serve.log 2>&1 &) \
          && for _ in \$(seq 60); do curl -sf -H 'Host: test_site' http://127.0.0.1:8000/api/method/ping && break; sleep 1; done \
          && curl -sf -H 'Host: test_site' http://127.0.0.1:8000/api/method/ping" \
        || echo "WARNING: frappe smoke check failed") \
    ; pkill -f 'bench serve' ; pkill -f 'frappe.utils.bench_helper' ; frappe-services stop
