# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors

from __future__ import unicode_literals
import frappe
from frappe.desk.page.setup_wizard.install_fixtures import update_genders_and_salutations

def execute():
	frappe.db.set_value("DocType", "Contact", "module", "Contacts")
	frappe.db.set_value("DocType", "Address", "module", "Contacts")
	frappe.db.set_value("DocType", "Address Template", "module", "Contacts")
	update_genders_and_salutations()