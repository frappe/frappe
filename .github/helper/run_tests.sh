#!/bin/bash

cd ~/frappe-bench/ || exit

if [ "$TYPE" == "server" ]; then

  if [ "$DB" == "mariadb" ]; then
    bench --verbose --site test_site run-tests --coverage
  fi

  if [ "$DB" == "postgres" ]; then
    bench --verbose --site test_site run-tests --coverage
  fi

fi

if [ "$TYPE" == "ui" ]; then
  bench --site test_site execute frappe.utils.install.complete_setup_wizard
  bench --site test_site run-ui-tests frappe --headless
fi