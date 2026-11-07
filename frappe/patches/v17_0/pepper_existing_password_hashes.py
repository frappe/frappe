# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from cryptography.fernet import Fernet

import frappe
from frappe.utils import cstr, encode
from frappe.utils.password import Auth, passlibctx


def execute():
	"""Pepper existing password hashes by encrypting them with the site's encryption key."""
	try:
		fernet = Fernet(frappe.local.conf.get("encryption_key") or "")
	except ValueError:
		# without a usable key the hashes stay plain, and are peppered on login once a key exists
		return

	rows = (
		frappe.qb.from_(Auth)
		.select(Auth.doctype, Auth.name, Auth.fieldname, Auth.password)
		.where(Auth.encrypted == 0)
		.run(as_dict=True)
	)

	for row in rows:
		# already peppered rows are not plain hashes, so running this skips them
		if not passlibctx.identify(row.password):
			continue

		frappe.qb.update(Auth).set(Auth.password, cstr(fernet.encrypt(encode(row.password)))).where(
			(Auth.doctype == row.doctype) & (Auth.name == row.name) & (Auth.fieldname == row.fieldname)
		).run()
