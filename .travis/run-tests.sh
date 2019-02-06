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

elif [[ $TEST_TYPE == 'ui' ]]; then
    setup_mariadb_env 'test_site_ui'
    bench --site test_site_ui --force restore ./apps/frappe/test_sites/test_site_ui/test_site_ui-database.sql.gz
    bench --site test_site_ui migrate
    bench --site test_site_ui scheduler disable
    cd apps/frappe && yarn && yarn cypress:run

elif [[ $DB == 'postgres' ]]; then
    psql -c "CREATE DATABASE test_frappe;" -U postgres
    psql -c "CREATE USER test_frappe WITH PASSWORD 'test_frappe';" -U postgres
    bench --site test_site_postgres reinstall --yes
    bench --site test_site_postgres scheduler disable
    bench --site test_site_postgres run-tests --coverage
fi
