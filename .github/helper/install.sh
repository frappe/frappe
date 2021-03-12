#!/bin/bash

cd ~
source ./.nvm/nvm.sh
nvm install v8.10.0

git clone https://github.com/frappe/bench --depth 1
pip install -e ./bench

bench init frappe-bench --skip-assets --python $(which python) --frappe-path ${GITHUB_WORKSPACE}

mkdir ~/frappe-bench/sites/test_site
cp ${GITHUB_WORKSPACE}/.github/helper/$DB.json ~/frappe-bench/sites/test_site/site_config.json

if [ $DB == "mariadb" ];then
  mysql --host 127.0.0.1 --port 3306 -u root -e "SET GLOBAL character_set_server = 'utf8mb4'";
  mysql --host 127.0.0.1 --port 3306 -u root -e "SET GLOBAL collation_server = 'utf8mb4_unicode_ci'";
  mysql --host 127.0.0.1 --port 3306 -u root -e "CREATE DATABASE test_frappe";
  mysql --host 127.0.0.1 --port 3306 -u root -e "CREATE USER 'test_frappe'@'localhost' IDENTIFIED BY 'test_frappe'";
  mysql --host 127.0.0.1 --port 3306 -u root -e "GRANT ALL PRIVILEGES ON \`test_frappe\`.* TO 'test_frappe'@'localhost'";
  mysql --host 127.0.0.1 --port 3306 -u root -e "UPDATE mysql.user SET Password=PASSWORD('travis') WHERE User='root'";
  mysql --host 127.0.0.1 --port 3306 -u root -e "FLUSH PRIVILEGES";
fi

if [ $DB == "postgres" ];then
    echo "travis" | psql -c "CREATE DATABASE test_frappe" -U postgres;
    echo "travis" | psql -c "CREATE USER test_frappe WITH PASSWORD 'test_frappe'" -U postgres;
fi

cd ./frappe-bench

sed -i 's/watch:/# watch:/g' Procfile
sed -i 's/schedule:/# schedule:/g' Procfile

if [ $TYPE == "server" ]; then sed -i 's/redis_socketio:/# redis_socketio:/g' Procfile; fi
if [ $TYPE == "server" ]; then sed -i 's/socketio:/# socketio:/g' Procfile; fi

if [ $TYPE == "ui" ]; then bench setup requirements --node; fi

bench start &
bench --site test_site reinstall --yes
bench build --app frappe