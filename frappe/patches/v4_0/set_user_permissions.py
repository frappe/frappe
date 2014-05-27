# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.core.page.user_permissions.user_permissions import add

def execute():
	if "match" in frappe.db.get_table_columns("DocPerm"):
		add_user_permissions_for_owner_match()


def add_user_permissions_for_owner_match():
	for dt, role in frappe.db.sql("""select distinct parent, role from `tabDocPerm` where `match`='owner'"""):
		for user in frappe.db.sql("""select distinct parent from `tabUserRole` where role=%s""", role):
			for name in frappe.db.sql_list("""select name from `tab{doctype}` where owner=%s""".format(dt), user):
				# add to user permissions
				add(user, dt, name)
