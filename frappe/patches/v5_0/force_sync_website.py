from __future__ import unicode_literals
import frappe
from frappe.website import statics

def execute():
	statics.sync_statics(rebuild=True)
