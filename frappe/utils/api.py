from functools import wraps

import frappe


def ignore_csrf(fn):
	"""
	Decorator to ignore CSRF for a particular method.
	"""

	@wraps(fn)
	def wrapped(*args, **kwargs):
		frappe.local.ignore_csrf = True
		return fn(*args, **kwargs)

	return wrapped
