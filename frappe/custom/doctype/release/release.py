# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe import _
from frappe.model.document import Document
from frappe.custom.doctype.package.package import export_package
from frappe.frappeclient import FrappeClient
from frappe.utils.file_manager import save_file
from frappe.model.naming import make_autoname
from frappe.utils.password import get_decrypted_password

class Release(Document):

	def create_release(self):
		package = export_package()

		for dt_file in frappe.get_list("File", filters={"attached_to_doctype": "Release", "attached_to_name": "Release"}):
			frappe.delete_doc_if_exists("File", dt_file.name)

		file_name = make_autoname("Package")
		save_file(file_name, json.dumps(package), "Release", "Release")

		length = len(self.instances)
		for idx, instance in enumerate(self.instances):
			frappe.publish_realtime("package",  {"progress": idx, "total": length, "message": instance.instance, "prefix": _("Deploying")},
				user=frappe.session.user)

			self.install_package_to_remote(package, instance)

	def install_package_to_remote(self, package, instance):
		remote = frappe.get_doc("Release Instance", instance.instance)
		connection = FrappeClient(remote.instance, remote.user, get_decrypted_password(remote.doctype, remote.name))

		try:
			connection.post_request({
				"cmd": "frappe.custom.doctype.package.package.import_package",
				"package": json.dumps(package)
			})
		except Exception as e:
			frappe.log_error(frappe.get_traceback())
			frappe.throw(_("Error while installing package to site {0}. Please check Error Logs.").format(remote.instance))
