#!/bin/bash
set -e

echo "Setting Up System Dependencies..."

echo "::group::apt packages"
if ! command -v redis-server > /dev/null || ! command -v mariadb > /dev/null; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq --fix-missing \
    libcups2-dev redis-server mariadb-client fontconfig libjpeg-turbo8 xfonts-75dpi xfonts-base
fi

install_wkhtmltopdf() {
  wget -q https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-2/wkhtmltox_0.12.6.1-2.jammy_amd64.deb
  sudo apt-get -qq install -y --no-install-recommends ./wkhtmltox_0.12.6.1-2.jammy_amd64.deb
}
install_wkhtmltopdf
echo "::endgroup::"
