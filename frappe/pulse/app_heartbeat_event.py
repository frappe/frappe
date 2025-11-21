import frappe
from frappe.modules import get_doctype_module
from frappe.pulse.utils import get_app_version, get_frappe_version
from frappe.utils.caching import site_cache

from .client import capture, is_enabled


def capture_app_heartbeat(req_params):
	if not should_capture():
		return

	method, doctype = get_method_and_doctype(req_params)
	if not method and not doctype:
		return

	app_name = get_app_name(method, doctype)
	if app_name and app_name != "frappe":
		capture(
			event_name="app_heartbeat",
			site=frappe.local.site,
			app=app_name,
			properties={
				"app_version": get_app_version(app_name),
				"frappe_version": get_frappe_version(),
			},
			interval="6h",
		)


def should_capture():
	if not is_enabled() or frappe.session.user in frappe.STANDARD_USERS:
		return False

	status_code = frappe.response.http_status_code or 0
	if status_code and not (200 <= status_code < 300):
		return False

	return True


def get_method_and_doctype(req_params):
	method = req_params.get("method") or frappe.form_dict.get("method")
	doctype = req_params.get("doctype") or frappe.form_dict.get("doctype")
	return method, doctype


def get_app_name(method, doctype):
	app_name = None
	if method and "." in method and not method.startswith("frappe."):
		app_name = method.split(".", 1)[0]

	if not app_name and doctype:
		module = get_doctype_module(doctype)
		app_name = app_module_map().get(module)

	return app_name


@site_cache()
def app_module_map():
	defs = frappe.get_all("Module Def", fields=["name", "app_name"])
	return {d.name: d.app_name for d in defs}
