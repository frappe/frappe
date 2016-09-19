from __future__ import unicode_literals
import frappe
from frappe.exceptions import DataError
from frappe.utils.password import get_decrypted_password
import json

app_list = [
	{"app_name": "razorpay_integration", "service_name": "Razorpay", "doctype": "Razorpay Settings", "remove": True},
	{"app_name": "paypal_integration", "service_name": "PayPal", "doctype": "PayPal Settings", "remove": True},
	{"app_name": "frappe", "service_name": "Dropbox Integration", "doctype": "Dropbox Backup", "remove": False}
]

def execute():
	frappe.reload_doc("integration_broker", "doctype", "integration_service")

	installed_apps = frappe.get_installed_apps()

	for app_details in app_list:
		if app_details["app_name"] in installed_apps:
			try:
				setup_integration_service(app_details)

			except DataError:
				pass

			finally:
				if app_details["remove"]:
					uninstall_app(app_details["app_name"])

	frappe.delete_doc("DocType", "Dropbox Backup")

def setup_integration_service(app_details):
	settings = get_app_settings(app_details)

	if not settings:
		raise DataError

	if frappe.db.exists("Integration Service", app_details["service_name"]):
		integration_service = frappe.get_doc("Integration Service", app_details["service_name"])
	else:
		integration_service = frappe.new_doc("Integration Service")
		integration_service.service = app_details["service_name"]

	integration_service.enabled = 1
	integration_service.custom_settings_json = json.dumps(settings) if settings else ''
	integration_service.flags.ignore_mandatory = True
	integration_service.save(ignore_permissions=True)

def get_app_settings(app_details):
	from frappe.integration_broker.doctype.integration_service.integration_service import get_integration_controller

	parameters = {}
	doctype = docname = app_details["doctype"]

	app_settings = get_parameters(app_details)
	settings = app_settings["settings"]

	controller = get_integration_controller(app_details["service_name"], setup=False)

	for d in controller.parameters_template:
		if settings.get(d.fieldname):
			if ''.join(set(settings.get(d.fieldname))) == '*':
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

	elif app_details["service_name"] == "Dropbox Integration":
		doc = frappe.db.get_value(app_details["doctype"], None,
			["dropbox_access_key", "dropbox_access_secret", "upload_backups_to_dropbox"], as_dict=1)

		if not (frappe.conf.dropbox_access_key and frappe.conf.dropbox_secret_key):
			raise DataError

		return {
			"settings": {
				"app_access_key": frappe.conf.dropbox_access_key,
				"app_secret_key": frappe.conf.dropbox_secret_key,
				"dropbox_access_key": doc.dropbox_access_key,
				"dropbox_access_secret": doc.dropbox_access_secret,
				"backup_frequency": doc.upload_backups_to_dropbox
			}
		}
