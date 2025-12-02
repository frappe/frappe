# Copyright (c) 2025, Frappe Technologies and Contributors
# License: MIT. See LICENSE

"""Set upload_public_files permission to 1 (checked) by default for all existing DocPerm entries"""

import frappe


def execute():
	"""Set upload_public_files=1 for all existing DocPerm and Custom DocPerm entries where it's not already set"""
	# Update all DocPerm entries where upload_public_files is 0 or NULL
	frappe.db.sql(
		"""
		UPDATE `tabDocPerm`
		SET `upload_public_files` = 1
		WHERE `upload_public_files` = 0 OR `upload_public_files` IS NULL
	"""
	)
	# Update all Custom DocPerm entries where upload_public_files is 0 or NULL
	frappe.db.sql(
		"""
		UPDATE `tabCustom DocPerm`
		SET `upload_public_files` = 1
		WHERE `upload_public_files` = 0 OR `upload_public_files` IS NULL
	"""
	)
	frappe.db.commit()
