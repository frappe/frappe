# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document


class PatchLog(Document):
	pass


def before_migrate():
	frappe.reload_doc("core", "doctype", "patch_log")
