#!/bin/bash
set -e
cd ~ || exit

echo "::group::Install Bench"
pip install frappe-bench
echo "::endgroup::"

echo "::group::Init Bench"
bench -v init frappe-bench --skip-assets --python "$(which python)" --frappe-path "${GITHUB_WORKSPACE}"
cd ./frappe-bench || exit

bench -v setup requirements --dev
if [ "$TYPE" == "ui" ]
then
  bench -v setup requirements --node;
fi
echo "::endgroup::"

echo "::group::Create Test Site"
mkdir ~/frappe-bench/sites/test_site
cp "${GITHUB_WORKSPACE}/.github/helper/db/$DB.json" ~/frappe-bench/sites/test_site/site_config.json

if [ "$DB" == "mariadb" ]
then
  mariadb --host 127.0.0.1 --port 3306 -u root -ptravis -e "SET GLOBAL character_set_server = 'utf8mb4'";
  mariadb --host 127.0.0.1 --port 3306 -u root -ptravis -e "SET GLOBAL collation_server = 'utf8mb4_unicode_ci'";

  mariadb --host 127.0.0.1 --port 3306 -u root -ptravis -e "CREATE DATABASE test_frappe";
  mariadb --host 127.0.0.1 --port 3306 -u root -ptravis -e "CREATE USER 'test_frappe'@'localhost' IDENTIFIED BY 'test_frappe'";
  mariadb --host 127.0.0.1 --port 3306 -u root -ptravis -e "GRANT ALL PRIVILEGES ON \`test_frappe\`.* TO 'test_frappe'@'localhost'";

  mariadb --host 127.0.0.1 --port 3306 -u root -ptravis -e "FLUSH PRIVILEGES";
fi
if [ "$DB" == "postgres" ]
then
  echo "travis" | psql -h 127.0.0.1 -p 5432 -c "CREATE DATABASE test_frappe" -U postgres;
  echo "travis" | psql -h 127.0.0.1 -p 5432 -c "CREATE USER test_frappe WITH PASSWORD 'test_frappe'" -U postgres;
fi
echo "::endgroup::"

echo "::group::Modify processes"
sed -i 's/^watch:/# watch:/g' Procfile
sed -i 's/^schedule:/# schedule:/g' Procfile

if [ "$TYPE" == "server" ]
then
  sed -i 's/^socketio:/# socketio:/g' Procfile
  sed -i 's/^redis_socketio:/# redis_socketio:/g' Procfile
fi

if [ "$TYPE" == "ui" ]
then
  sed -i 's/^web: bench serve/web: bench serve --with-coverage/g' Procfile
fi
echo "::endgroup::"

bench start &> ~/frappe-bench/bench_start.log &

echo "::group::Install site"
if [ "$TYPE" == "server" ]
then
  CI=Yes bench build --app frappe &
  build_pid=$!
fi

bench --site test_site reinstall --yes

if [ "$TYPE" == "server" ]
then
  # wait till assets are built succesfully
  wait $build_pid
fi
echo "::endgroup::"
