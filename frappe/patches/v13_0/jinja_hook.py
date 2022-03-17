# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from click import secho

def execute():
	if frappe.get_hooks('jenv'):
		print()
		secho('WARNING: The hook "jenv" is deprecated. Follow the migration guide to use the new "jinja" hook.', fg='yellow')
		secho('https://github.com/frappe/frappe/wiki/Migrating-to-Version-13', fg='yellow')
		print()
