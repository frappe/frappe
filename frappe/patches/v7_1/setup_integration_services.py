from __future__ import unicode_literals
import frappe
from frappe.exceptions import DataError
from frappe.utils.password import get_decrypted_password
from frappe.utils import cstr
import os

app_list = [
	{"app_name": "razorpay_integration", "service_name": "Razorpay", "doctype": "Razorpay Settings", "remove": True},
	{"app_name": "paypal_integration", "service_name": "PayPal", "doctype": "PayPal Settings", "remove": True},
	{"app_name": "frappe", "service_name": "Dropbox", "doctype": "Dropbox Backup", "remove": False}
]

def execute():
	installed_apps = frappe.get_installed_apps()

	for app_details in app_list:
		if app_details["app_name"] in installed_apps:
			settings = get_app_settings(app_details)
			if app_details["remove"]:
				uninstall_app(app_details["app_name"])

			try:
				setup_integration_service(app_details, settings)
			except DataError:
				pass

	frappe.delete_doc("DocType", "Dropbox Backup")

def setup_integration_service(app_details, settings=None):
	if not settings:
		return

	setup_service_settings(app_details["service_name"], settings)

	doc_path = frappe.get_app_path("frappe", "integration_broker", "doctype",
		"integration_service", "integration_service.json")

	if not os.path.exists(doc_path):
		return

	frappe.reload_doc("integration_broker", "doctype", "integration_service")

	if frappe.db.exists("Integration Service", app_details["service_name"]):
		integration_service = frappe.get_doc("Integration Service", app_details["service_name"])
	else:
		integration_service = frappe.new_doc("Integration Service")
		integration_service.service = app_details["service_name"]

	integration_service.enabled = 1
	integration_service.flags.ignore_mandatory = True
	integration_service.save(ignore_permissions=True)

def get_app_settings(app_details):
	parameters = {}
	doctype = docname = app_details["doctype"]

	app_settings = get_parameters(app_details)
	if app_settings:
		settings = app_settings["settings"]
		frappe.reload_doc("integrations", "doctype", "{0}_settings".format(app_details["service_name"].lower()))
		controller = frappe.get_meta("{0} Settings".format(app_details["service_name"]))

		for d in controller.fields:
			if settings.get(d.fieldname):
				if ''.join(set(cstr(settings.get(d.fieldname)))) == '*':
					setattr(settings, d.fieldname, get_decrypted_password(doctype, docname, d.fieldname, raise_exception=True))

				parameters.update({d.fieldname : settings.get(d.fieldname)})

	return parameters

def uninstall_app(app_name):
	from frappe.installer import remove_from_installed_apps
	remove_from_installed_apps(app_name)

def get_parameters(app_details):
	if app_details["service_name"] == "Razorpay":
		return {"settings": frappe.get_doc(app_details["doctype"])}

	elif app_details["service_name"] == "PayPal":
		if frappe.conf.paypal_username and frappe.conf.paypal_password and frappe.conf.paypal_signature:
			return {
				"settings": {
					"api_username": frappe.conf.paypal_username,
					"api_password": frappe.conf.paypal_password,
					"signature": frappe.conf.paypal_signature
				}
			}
		else:
			return {"settings": frappe.get_doc(app_details["doctype"])}

	elif app_details["service_name"] == "Dropbox":
		doc = frappe.db.get_value(app_details["doctype"], None,
			["dropbox_access_key", "dropbox_access_secret", "upload_backups_to_dropbox"], as_dict=1)

		if not doc:
			return

		if not (frappe.conf.dropbox_access_key and frappe.conf.dropbox_secret_key):
			return

		return {
			"settings": {
				"app_access_key": frappe.conf.dropbox_access_key,
				"app_secret_key": frappe.conf.dropbox_secret_key,
				"dropbox_access_key": doc.dropbox_access_key,
				"dropbox_access_secret": doc.dropbox_access_secret,
				"backup_frequency": doc.upload_backups_to_dropbox,
				"enabled": doc.send_backups_to_dropbox
			}
		}

def setup_service_settings(service_name, settings):
	service_doc = frappe.get_doc("{0} Settings".format(service_name))
	service_doc.update(settings)
	service_doc.flags.ignore_mandatory = True
	service_doc.save(ignore_permissions=True)