#!/bin/bash

set -e

setup_mariadb_env() {
    mysql -u root -ptravis -e "create database $1"
    mysql -u root -ptravis -e "USE mysql; CREATE USER '$1'@'localhost' IDENTIFIED BY '$1'; FLUSH PRIVILEGES; "
    mysql -u root -ptravis -e "USE mysql; GRANT ALL PRIVILEGES ON \`$1\`.* TO '$1'@'localhost';"
}

if [[ $DB == 'mariadb' ]]; then
    setup_mariadb_env 'test_frappe'
    bench --site test_site reinstall --yes
    bench --site test_site scheduler disable
    bench --site test_site run-tests --coverage
