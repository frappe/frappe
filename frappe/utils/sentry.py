import frappe


def add_bootinfo(bootinfo):
	"""Called from hook, sends DSN so client side can setup error monitoring.

	Config needs to be present in site_config in following format:

	"error_reporting": {
	        "sentry": {
	                "dsn": "...",
	                ...
	        }
	}
	"""
	if not frappe.get_system_settings("auto_report_errors"):
		return

	sentry_info = (frappe.conf.get("error_reporting") or {}).get("sentry")
	if sentry_info:
		bootinfo.sentry = sentry_info
