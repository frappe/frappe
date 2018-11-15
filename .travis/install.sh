#!/bin/bash

set -e

sudo rm /etc/apt/sources.list.d/mongodb*.list
sudo rm /etc/apt/sources.list.d/docker.list
sudo apt-get install hhvm && rm -rf /home/travis/.kiex/
sudo apt-get purge -y mysql-common mysql-server mysql-client
source ~/.nvm/nvm.sh
nvm install v8.10.0

pip install python-coveralls

wget https://raw.githubusercontent.com/frappe/bench/master/playbooks/install.py

sudo python install.py --develop --user travis --without-bench-setup
sudo pip install -e ~/bench

rm $TRAVIS_BUILD_DIR/.git/shallow
cd ~/ && bench init frappe-bench --python $(which python) --frappe-path $TRAVIS_BUILD_DIR
cp -r $TRAVIS_BUILD_DIR/test_sites/test_site ~/frappe-bench/sites/
cp -r $TRAVIS_BUILD_DIR/test_sites/test_site_postgres ~/frappe-bench/sites/
cp -r $TRAVIS_BUILD_DIR/test_sites/test_site_ui ~/frappe-bench/sites/