# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""The /flow page: the built Vite entry (index.html, copied here by `yarn build`) with the
signed-in user's boot data rendered into it."""

from urllib.parse import urlencode

import frappe
from frappe import _

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		# back to the page asked for, such as a chat someone shared
		frappe.local.flags.redirect_location = f"/login?{urlencode({'redirect-to': frappe.request.path})}"
		raise frappe.Redirect
	context.boot = get_boot()
	return context


@frappe.whitelist(methods=["POST"], allow_guest=True)  # nosemgrep: guest-whitelisted-method
def get_context_for_dev():
	"""The same boot data for the Vite dev server, which cannot render the page template."""
	if not frappe.conf.developer_mode:
		frappe.throw(_("Only available in developer mode."), frappe.PermissionError)
	return get_boot()


def get_boot() -> dict:
	from frappe.flow.api import boot

	csrf_token = frappe.sessions.get_csrf_token()
	frappe.db.commit()  # the token is written to the session on first use, as /app does; nosemgrep: frappe-manual-commit
	return {
		"csrf_token": csrf_token,
		"site_name": frappe.local.site,
		"socketio_port": frappe.conf.socketio_port,
		"flow_boot": boot(),
	}
