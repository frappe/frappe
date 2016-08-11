from __future__ import unicode_literals
import frappe
from frappe.exceptions import DataError
from frappe.utils.password import get_decrypted_password

def execute():
	if not frappe.db.exists("DocType", "Integration Service"):
		return
	
	installed_apps = frappe.get_installed_apps()
	print installed_apps
	for app_details in [{"app_name": "razorpay_integration", "service_name": "Razorpay"},
		{"app_name":"paypal_integration", "service_name": "PayPal"}]:
		if app_details["app_name"] in installed_apps:
			try:
				setup_integration_service(app_details)
				uninstall_app(app_details["app_name"])
			except Exception:
				pass

def setup_integration_service(app_details):
	settings = get_app_settings(app_details["service_name"])

	if not settings:
		raise DataError
	
	if frappe.db.exists("Integration Service", app_details["service_name"]):
		integration_service = frappe.get_doc("Integration Service", app_details["service_name"])
	else:
		integration_service = frappe.new_doc("Integration Service")
		integration_service.service = app_details["service_name"]
	
	integration_service.enabled = 1
	integration_service.set("parameters", [])
	integration_service.extend("parameters", settings)
	integration_service.flags.ignore_mandatory = True
	integration_service.save(ignore_permissions=True)

def get_app_settings(service_name):
	from frappe.integration_broker.doctype.integration_service.integration_service import get_integration_controller
	
	parameters = []
	doctype = docname = "{0} Settings".format(service_name)
	settings = frappe.get_doc(doctype)
	controller = get_integration_controller(service_name, setup=False)
	
	if not settings.get(controller.parameters_template[0]["fieldname"]) and service_name == "PayPal":
		settings = { "api_username": frappe.conf.paypal_username, "api_password": frappe.conf.paypal_password,
			"signature": frappe.conf.paypal_signature }
	
	for d in controller.parameters_template:
		if not settings.get(d.fieldname):
			raise DataError

		if ''.join(set(settings.get(d.fieldname))) == '*':
			setattr(settings, d.fieldname, get_decrypted_password(doctype, docname, d.fieldname, raise_exception=False))

		parameters.append({'label': d.label, 'fieldname': d.fieldname, "value": settings.get(d.fieldname)})
	
	return parameters

def uninstall_app(app_name):
	from frappe.installer import remove_from_installed_apps
	remove_from_installed_apps(app_name)