from __future__ import unicode_literals
import frappe

def execute():
	frappe.db.sql("""delete from `__global_search` where doctype='Static Web Page'""");