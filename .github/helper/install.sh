#!/bin/bash
set -e
cd ~ || exit

echo "Setting Up Bench..."

pip install frappe-bench
bench -v init frappe-bench --skip-assets --python "$(which python)" --frappe-path "${GITHUB_WORKSPACE}"
cd ./frappe-bench || exit

bench -v setup requirements --dev
if [ "$TYPE" == "ui" ]; then
  bench -v setup requirements --node;
fi

echo "Setting Up Sites & Database..."

mkdir ~/frappe-bench/sites/test_site
cp "${GITHUB_WORKSPACE}/.github/helper/consumer_db/$DB.json" ~/frappe-bench/sites/test_site/site_config.json

if [ "$TYPE" == "server" ]; then
  mkdir ~/frappe-bench/sites/test_site_producer;
  cp "${GITHUB_WORKSPACE}/.github/helper/producer_db/$DB.json" ~/frappe-bench/sites/test_site_producer/site_config.json;
fi
if [ "$DB" == "mariadb" ];then
  mariadb --host 127.0.0.1 --port 3306 -u root -ptravis -e "SET GLOBAL character_set_server = 'utf8mb4'";
  mariadb --host 127.0.0.1 --port 3306 -u root -ptravis -e "SET GLOBAL collation_server = 'utf8mb4_unicode_ci'";

  mariadb --host 127.0.0.1 --port 3306 -u root -ptravis -e "CREATE DATABASE test_frappe_consumer";
  mariadb --host 127.0.0.1 --port 3306 -u root -ptravis -e "CREATE USER 'test_frappe_consumer'@'localhost' IDENTIFIED BY 'test_frappe_consumer'";
  mariadb --host 127.0.0.1 --port 3306 -u root -ptravis -e "GRANT ALL PRIVILEGES ON \`test_frappe_consumer\`.* TO 'test_frappe_consumer'@'localhost'";

  mariadb --host 127.0.0.1 --port 3306 -u root -ptravis -e "CREATE DATABASE test_frappe_producer";
  mariadb --host 127.0.0.1 --port 3306 -u root -ptravis -e "CREATE USER 'test_frappe_producer'@'localhost' IDENTIFIED BY 'test_frappe_producer'";
  mariadb --host 127.0.0.1 --port 3306 -u root -ptravis -e "GRANT ALL PRIVILEGES ON \`test_frappe_producer\`.* TO 'test_frappe_producer'@'localhost'";

  mariadb --host 127.0.0.1 --port 3306 -u root -ptravis -e "FLUSH PRIVILEGES";
fi
if [ "$DB" == "postgres" ];then
  echo "travis" | psql -h 127.0.0.1 -p 5432 -c "CREATE DATABASE test_frappe_consumer" -U postgres;
  echo "travis" | psql -h 127.0.0.1 -p 5432 -c "CREATE USER test_frappe_consumer WITH PASSWORD 'test_frappe'" -U postgres;

  echo "travis" | psql -h 127.0.0.1 -p 5432 -c "CREATE DATABASE test_frappe_producer" -U postgres;
  echo "travis" | psql -h 127.0.0.1 -p 5432 -c "CREATE USER test_frappe_producer WITH PASSWORD 'test_frappe'" -U postgres;
fi

echo "Setting Up Procfile..."

sed -i 's/^watch:/# watch:/g' Procfile
sed -i 's/^schedule:/# schedule:/g' Procfile
if [ "$TYPE" == "server" ]; then
  sed -i 's/^socketio:/# socketio:/g' Procfile;
  sed -i 's/^redis_socketio:/# redis_socketio:/g' Procfile;
fi

echo "Starting Bench..."
export FRAPPE_TUNE_GC=True

bench start &> bench_start.log &
bench --site test_site reinstall --yes

if [ "$TYPE" == "server" ]; then
  bench --site test_site_producer reinstall --yes;
  CI=Yes bench build --app frappe;
fi
