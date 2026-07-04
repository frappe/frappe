FROM python:3.14-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    UV_TOOL_BIN_DIR=/usr/local/bin \
    UV_TOOL_DIR=/opt/uv/tools \
    BROWSER_PATH=/usr/bin/google-chrome

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

RUN curl -fsSL https://deb.nodesource.com/setup_24.x | bash - \
    && curl -LsS https://r.mariadb.com/downloads/mariadb_repo_setup | bash -s -- --mariadb-server-version="mariadb-11.8.5" --skip-maxscale \
    && echo "deb http://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc -o /etc/apt/trusted.gpg.d/pgdg.asc \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && curl -fsSL https://dl.google.com/linux/linux_signing_key.pub -o /etc/apt/trusted.gpg.d/google-chrome.asc \
    && apt-get -qq update \
    && apt-get -qq install -y --no-install-recommends \
        nodejs \
        google-chrome-stable \
        redis-server \
        mariadb-client \
        libmariadb-dev \
        postgresql-client-18 \
        libpq-dev \
        libcups2-dev \
        libgtk-3-0 \
        libgbm1 \
        libnotify4 \
        libnss3 \
        libxss1 \
        libasound2 \
        libxtst6 \
        xauth \
        xvfb \
        zip \
    && curl -fsSL -o /tmp/wkhtmltox.deb https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox_0.12.6.1-3.bookworm_amd64.deb \
    && apt-get -qq install -y /tmp/wkhtmltox.deb \
    && rm /tmp/wkhtmltox.deb \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g yarn \
    && uv tool install frappe-bench

ENV PATH="/usr/lib/postgresql/18/bin:${PATH}"
