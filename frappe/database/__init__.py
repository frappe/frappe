# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# Database Module
# --------------------

from __future__ import unicode_literals

import frappe
import frappe.database.postgres
import frappe.database.mariadb

def setup_database(force, verbose):
	if frappe.conf.db_type == 'postgres':
		return frappe.database.postgres.setup_database(force, verbose)
	else:
		return frappe.database.mariadb.setup_database(force, verbose)

def drop_user_and_database(db_name, root_login=None, root_password=None):
	if frappe.conf.db_type == 'postgres':
		pass
	else:
		return frappe.database.mariadb.drop_user_and_database(db_name, root_login, root_password)

def get_db(host=None, user=None, password=None):
	if frappe.conf.db_type == 'postgres':
		return frappe.database.postgres.PostgresDatabase(host, user, password)
	else:
		return frappe.database.mariadb.MariadbDatabase(host, user, password)
