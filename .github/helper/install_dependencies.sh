#!/bin/bash
set -e

echo "Setting Up System Dependencies..."

sudo apt-get update
sudo apt-get -y remove mysql-server mysql-client
sudo apt-get -y install libcups2-dev redis-server mariadb-client-10.6

install_wkhtmltopdf() {
  wget -q https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox_0.12.6-1.focal_amd64.deb
  sudo dpkg -i install ./wkhtmltox_0.12.6-1.focal_amd64.deb
}
install_wkhtmltopdf &
