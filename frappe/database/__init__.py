# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# Database Module
# --------------------

from __future__ import unicode_literals

import frappe

def setup_database(force, verbose):
	if frappe.conf.db_type == 'postgres':
		from frappe.database.postgres import setup_database as _setup_database
		return _setup_database(force, verbose)
	else:
		from frappe.database.mariadb import setup_database as _setup_database
		return _setup_database(force, verbose)

def get_db(host=None, user=None, password=None):
	if frappe.conf.db_type == 'postgres':
		from frappe.database.postgres import PostgresDatabase
		return PostgresDatabase(host, user, password)
	else:
		from frappe.database.mariadb import MariadbDatabase
		return MariadbDatabase(host, user, password)
