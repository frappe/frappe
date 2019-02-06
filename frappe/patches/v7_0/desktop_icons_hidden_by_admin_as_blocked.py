from __future__ import unicode_literals
import frappe

def execute():
	# all icons hidden in standard are "blocked"
	# this is for the use case where the admin wants to remove icon for everyone

	# in 7.0, icons may be hidden by default, but still can be shown to the user
	# e.g. Accounts, Stock etc, so we need a new property for blocked

	if frappe.db.table_exists('Desktop Icon'):
		frappe.db.sql('update `tabDesktop Icon` set blocked = 1 where standard=1 and hidden=1')