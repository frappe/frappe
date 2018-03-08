from __future__ import unicode_literals

import functools
import frappe
from past.builtins import cmp

@frappe.whitelist()
def get_help_messages():
	'''Return help messages for the desktop (called via `get_help_messages` hook)

	Format for message:

		{
			title: _('Add Employees to Manage Them'),
			description: _('Add your Employees so you can manage leaves, expenses and payroll'),
			action: 'Add Employee',
			route: 'List/Employee'
		}

	'''
	messages = []
	for fn in frappe.get_hooks('get_help_messages'):
		messages += frappe.get_attr(fn)()

	return sorted(messages, key = functools.cmp_to_key(lambda a, b: cmp(a.get('count'), b.get('count'))))
