#!/bin/bash
set -e

echo "Setting Up System Dependencies..."

<<<<<<< HEAD
=======
sudo apt update
sudo apt install libcups2-dev redis-server mariadb-client-10.6

>>>>>>> 7484ebacb5 (ci(deps): install mariadb 10.6 (#19166))
install_wkhtmltopdf() {
  wget https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox_0.12.6-1.focal_amd64.deb
  sudo apt install ./wkhtmltox_0.12.6-1.focal_amd64.deb
}
install_wkhtmltopdf &


sudo apt update
sudo apt install libcups2-dev redis-server mariadb-client-10.3
