from __future__ import unicode_literals
import frappe
from frappe import _

def get_context(context):
	client_apps = frappe.get_all("OAuth Client", fields=["*"])
	if frappe.session.user == 'Guest':
		frappe.throw(_("You need to be logged in to access this page"), frappe.PermissionError)

	context.apps = client_apps
	context.show_sidebar=True
