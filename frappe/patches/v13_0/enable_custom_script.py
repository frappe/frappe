# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe


def execute():
	"""Enable all the existing Client script"""

	frappe.db.sql(
		"""
		UPDATE `tabClient Script` SET enabled=1
	"""
	)
