# Copyright (c) 2015, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document


class HasRole(Document):
	def before_insert(self):
		if frappe.db.exists("Has Role", {"parent": self.parent, "role": self.role}):
			frappe.throw(frappe._("User '{0}' already has the role '{1}'").format(self.parent, self.role))
