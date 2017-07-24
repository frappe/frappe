from __future__ import unicode_literals
import frappe

def get_context(context):
	client_apps = frappe.get_all("OAuth Client", fields=["*"])
	if frappe.session.user=='Guest':
		frappe.throw(_("You need to be logged in to access this page"), frappe.PermissionError)

	context.show_sidebar=True
	context.apps = client_apps
