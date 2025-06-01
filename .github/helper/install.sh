#!/bin/bash
set -e
cd ~ || exit

echo "::group::Install Bench"
pip install nts-bench
echo "::endgroup::"

echo "::group::Init Bench"
bench -v init nts-bench --skip-assets --python "$(which python)" --nts-path "${GITHUB_WORKSPACE}"
cd ./nts-bench || exit

bench -v setup requirements --dev
if [ "$TYPE" == "ui" ]
then
  bench -v setup requirements --node;
fi
echo "::endgroup::"

echo "::group::Create Test Site"
mkdir ~/nts-bench/sites/test_site
cp "${GITHUB_WORKSPACE}/.github/helper/db/$DB.json" ~/nts-bench/sites/test_site/site_config.json

if [ "$DB" == "mariadb" ]
then
  mariadb --host 127.0.0.1 --port 3306 -u root -ptravis -e "SET GLOBAL character_set_server = 'utf8mb4'";
  mariadb --host 127.0.0.1 --port 3306 -u root -ptravis -e "SET GLOBAL collation_server = 'utf8mb4_unicode_ci'";

  mariadb --host 127.0.0.1 --port 3306 -u root -ptravis -e "CREATE DATABASE test_nts";
  mariadb --host 127.0.0.1 --port 3306 -u root -ptravis -e "CREATE USER 'test_nts'@'localhost' IDENTIFIED BY 'test_nts'";
  mariadb --host 127.0.0.1 --port 3306 -u root -ptravis -e "GRANT ALL PRIVILEGES ON \`test_nts\`.* TO 'test_nts'@'localhost'";

  mariadb --host 127.0.0.1 --port 3306 -u root -ptravis -e "FLUSH PRIVILEGES";
fi
if [ "$DB" == "postgres" ]
then
  echo "travis" | psql -h 127.0.0.1 -p 5432 -c "CREATE DATABASE test_nts" -U postgres;
  echo "travis" | psql -h 127.0.0.1 -p 5432 -c "CREATE USER test_nts WITH PASSWORD 'test_nts'" -U postgres;
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

bench start &> ~/nts-bench/bench_start.log &

echo "::group::Install site"
if [ "$TYPE" == "server" ]
then
  CI=Yes bench build --app nts &
  build_pid=$!
fi

bench --site test_site reinstall --yes

if [ "$TYPE" == "server" ]
then
  # wait till assets are built succesfully
  wait $build_pid
fi
echo "::endgroup::"
