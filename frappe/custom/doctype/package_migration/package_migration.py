# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.frappeclient import FrappeClient
from frappe.model.document import Document
from frappe import _

class PackageMigration(Document):

	def install_package_to_remote(self, remote_instance, user, password):
		connection = FrappeClient(remote_instance, user, password)

		package_file = frappe.get_all("File", filters={
			"attached_to_doctype": "Package Migration",
			"attached_to_name": "Package Migration"
		}, limit=1, order_by="creation desc")

		try:
			connection.post_request({
				"cmd": "frappe.custom.doctype.package.package.import_package",
				"package": frappe.get_doc("File", package_file[0].name).get_content()
			})
		except Exception:
			frappe.log_error(frappe.get_traceback())
			frappe.throw(_("Could not connect to Remote Site."))
