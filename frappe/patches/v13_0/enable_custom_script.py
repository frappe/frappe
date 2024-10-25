# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe


def execute() -> None:
	"""Enable all the existing Client script"""

	frappe.db.sql(
		"""
		UPDATE `tabClient Script` SET enabled=1
	"""
	)
