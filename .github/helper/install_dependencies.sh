#!/bin/bash
set -e

echo "Setting Up System Dependencies..."

wget https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox_0.12.6-1.focal_amd64.deb
sudo apt install ./wkhtmltox_0.12.6-1.focal_amd64.deb

sudo apt update
sudo apt install libcups2-dev redis-server mariadb-client-10.3
