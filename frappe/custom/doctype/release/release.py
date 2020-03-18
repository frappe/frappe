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
		package = export_package().get("data")

		for dt_file in frappe.get_list("File", filters={"attached_to_doctype": "Release", "attached_to_name": "Release"}):
			frappe.delete_doc_if_exists("File", dt_file.name)

		file_name = make_autoname("Package")
		save_file(file_name, json.dumps(package), "Release", "Release")

		length = len(self.instances)
		for instance in self.instances:
			message = _("Releasing to {0}").format(instance.instance)
			frappe.publish_realtime("exporting_package", {"progress": idx, "total": length, "message": message},
				user=frappe.session.user)
			remote = frappe.get_doc("Remote Instance", instance.instance)
			self.install_package_to_remote(remote.instance, remote.user, get_decrypted_password(remote.doctype, remote.name))

	def install_package_to_remote(self, remote_instance, user, password):
		connection = FrappeClient(remote_instance, user, password)

		try:
			connection.post_request({
				"cmd": "frappe.custom.doctype.package.package.import_package",
				"package": package
			})
		except Exception:
			frappe.log_error(frappe.get_traceback())
			frappe.throw(_("Could not connect to Site {0}.").format(remote_instance))
