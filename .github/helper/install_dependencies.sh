#!/bin/bash

set -e

# python "${GITHUB_WORKSPACE}/.github/helper/roulette.py"
# if [[ $? != 2 ]];then
#   exit;
# fi

 # install wkhtmltopdf
wget -O /tmp/wkhtmltox.tar.xz https://github.com/frappe/wkhtmltopdf/raw/master/wkhtmltox-0.12.3_linux-generic-amd64.tar.xz
tar -xf /tmp/wkhtmltox.tar.xz -C /tmp
sudo mv /tmp/wkhtmltox/bin/wkhtmltopdf /usr/local/bin/wkhtmltopdf
sudo chmod o+x /usr/local/bin/wkhtmltopdf

# install cups
sudo apt-get install libcups2-dev

# install redis
sudo apt-get install redis-server

