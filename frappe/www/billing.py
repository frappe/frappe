import frappe
from frappe.utils import cint

no_cache = 1


def get_context(context):
	frappe.db.commit()  # nosemgrep
	context = frappe._dict()
	context.boot = get_boot()
	return context


def get_boot():
	return frappe._dict(
		{
			"site_name": frappe.local.site,
			"read_only_mode": frappe.flags.read_only,
			"csrf_token": frappe.sessions.get_csrf_token(),
			"setup_complete": frappe.is_setup_complete(),
		}
	)
