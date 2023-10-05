#!/bin/bash
set -e

echo "Setting Up System Dependencies..."

# sudo apt-get update
echo "List of repositories:" && (sudo apt-get update 2>&1 | grep 'Hit:')
upgrade_info=$(sudo apt-get -s upgrade)
packages_upgradable=$(echo "$upgrade_info" | grep -oP '\d+(?= upgraded)')
echo "$packages_upgradable packages can be upgraded:"
packages_list=$(echo "$upgrade_info" | grep -oP 'Inst \K\S+' | sed ':a;N;$!ba;s/\n/, /g' )
echo "${packages_list}."

sudo apt-get remove -y mysql-server mysql-client -q
sudo apt-get install -y libcups2-dev redis-server mariadb-client-10.6 -q

install_wkhtmltopdf() {
  wget -q https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox_0.12.6-1.focal_amd64.deb
  sudo apt install ./wkhtmltox_0.12.6-1.focal_amd64.deb
}
install_wkhtmltopdf &
