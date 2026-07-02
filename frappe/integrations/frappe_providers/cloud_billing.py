"""Billing: plan, usage and credit for the site. The bench pilot will proxy
these from Frappe Cloud Central; that route is the last piece to land, so for
now this returns an unavailable summary and the tab degrades gracefully."""

import frappe


def summary() -> dict:
	"""Billing summary for the site. Returns ``available: False`` until the
	bench exposes a billing route backed by Central."""
	return {"available": False, "manage_url": frappe.conf.get("cloud_account_url")}
