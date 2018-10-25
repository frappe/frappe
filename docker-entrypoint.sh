#!/bin/sh

function checkEnv() {
  if [[ -z "$DB_HOST" ]]; then
    echo "DB_HOST is not set"
    exit 1
  fi
  if [[ -z "$DB_PASSWORD" ]]; then
    echo "DB_PASSWORD is not set"
    exit 1
  fi
  if [[ -z "$ADMIN_PASSWORD" ]]; then
    echo "ADMIN_PASSWORD is not set"
    exit 1
  fi
  if [[ -z "$REDIS_QUEUE" ]]; then
    echo "REDIS_QUEUE is not set"
    exit 1
  fi
  if [[ -z "$REDIS_SOCKETIO" ]]; then
    echo "REDIS_SOCKETIO is not set"
    exit 1
  fi
  if [[ -z "$REDIS_CACHE" ]]; then
    echo "REDIS_CACHE is not set"
    exit 1
  fi
}

function checkConnection() {
  # Wait for mariadb
  dockerize -wait tcp://$DB_HOST:3306 -timeout 30s

  # Wait for all redis
  dockerize -wait tcp://$REDIS_QUEUE:11000 -timeout 30s
  dockerize -wait tcp://$REDIS_SOCKETIO:12000 -timeout 30s
  dockerize -wait tcp://$REDIS_CACHE:13000 -timeout 30s
}

function configureBench() {
  # set common config
  bench config set-common-config -c db_host $DB_HOST
  bench config set-common-config -c redis_queue "redis://$REDIS_QUEUE:11000"
  bench config set-common-config -c redis_socketio "redis://$REDIS_SOCKETIO:12000"
  bench config set-common-config -c redis_cache "redis://$REDIS_CACHE:13000"

  # set procfile
  rm Procfile
  bench setup procfile
  tail -n +4 Procfile > Procfile.1
  mv Procfile.1 Procfile
}

if [ "$1" = 'new-site' ]; then
  # Validate if DB_HOST is set.
  checkEnv
  # Validate DB Connection
  checkConnection
  # configure bench
  configureBench

  bench new-site --mariadb-root-password $DB_PASSWORD --admin-password $ADMIN_PASSWORD "$2"
fi

if [ "$1" = 'start' ]; then
  # Validate if DB_HOST is set.
  checkEnv
  # Validate DB Connection
  checkConnection
  # configure bench
  configureBench
  
  bench start
fi

if [ "$1" = 'migrate' ]; then
  # Validate if DB_HOST is set.
  checkEnv
  # Validate DB Connection
  checkConnection
  # configure bench
  configureBench

  bench --site "$2" migrate
fi

exec "$@"
