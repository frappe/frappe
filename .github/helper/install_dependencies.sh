#!/bin/bash
set -e

echo "Setting Up System Dependencies..."

echo "::group::apt packages"
install_wkhtmltopdf() {
  wget -q https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-2/wkhtmltox_0.12.6.1-2.jammy_amd64.deb
  sudo apt-get -qq install -y --no-install-recommends ./wkhtmltox_0.12.6.1-2.jammy_amd64.deb
}
install_wkhtmltopdf &
echo "::endgroup::"
