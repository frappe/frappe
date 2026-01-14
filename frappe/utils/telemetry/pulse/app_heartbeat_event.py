import frappe
from frappe.utils import get_app_version, get_frappe_version

from .client import capture, is_enabled


def capture_app_heartbeat(app):
	if not should_capture():
		return

	if app and app != "frappe":
		capture(
			event_name="app_heartbeat",
			site=frappe.local.site,
			app=app,
			properties={
				"app_version": get_app_version(app),
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
