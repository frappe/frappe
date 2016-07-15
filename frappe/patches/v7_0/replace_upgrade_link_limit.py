from __future__ import unicode_literals
import frappe
from frappe.limits import get_limits, clear_limit, update_limits

def execute():
	limits = get_limits()
	if limits and limits.upgrade_link:
		upgrade_url = limits.upgrade_link
		clear_limit('upgrade_link')
		update_limits({'upgrade_url': upgrade_url})
