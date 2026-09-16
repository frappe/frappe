# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""The /flow page: the built Vite entry (index.html, copied here by `yarn build`) with the
signed-in user's boot data rendered into it."""

import frappe
from frappe import _

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/flow"
		raise frappe.Redirect
	context.boot = get_boot()
	return context


@frappe.whitelist(methods=["POST"], allow_guest=True)
def get_context_for_dev():
	"""The same boot data for the Vite dev server, which cannot render the page template."""
	if not frappe.conf.developer_mode:
		frappe.throw(_("Only available in developer mode."), frappe.PermissionError)
	return get_boot()


def get_boot() -> dict:
	from flow.api import boot

	csrf_token = frappe.sessions.get_csrf_token()
	frappe.db.commit()  # the token is written to the session on first use, as /app does
	return {
		"csrf_token": csrf_token,
		"site_name": frappe.local.site,
		"socketio_port": frappe.conf.socketio_port,
		"flow_boot": boot(),
	}
