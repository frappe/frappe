# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors

from __future__ import unicode_literals
import frappe
from frappe.desk.page.setup_wizard.install_fixtures import update_genders

def execute():
	update_genders()