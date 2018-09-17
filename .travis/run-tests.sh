#!/bin/bash

set -ev
set -x

if [[ $DB == 'mariadb' ]]; then
    mysql -u root -ptravis -e 'create database test_frappe'
    echo "USE mysql;\nCREATE USER 'test_frappe'@'localhost' IDENTIFIED BY 'test_frappe';\nFLUSH PRIVILEGES;\n" | mysql -u root -ptravis
    echo "USE mysql;\nGRANT ALL PRIVILEGES ON \`test_frappe\`.* TO 'test_frappe'@'localhost';\n" | mysql -u root -ptravis
    bench --site test_site reinstall --yes
    bench --site test_site setup-help
    bench setup-global-help --root_password travis
    bench --site test_site scheduler disable
    bench --site test_site run-tests --coverage
elif [[ $DB == 'postgres' ]]; then
    psql -c "CREATE DATABASE test_frappe;" -U postgres
    psql -c "CREATE USER test_frappe WITH PASSWORD 'test_frappe';" -U postgres
    bench --site test_site_postgres reinstall --yes
    bench --site test_site_postgres setup-help
    bench setup-global-help --db_type=postgres --root_password travis
    bench --site test_site_postgres scheduler disable
    bench --site test_site_postgres run-tests --coverage
fi
