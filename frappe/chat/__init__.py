from __future__ import unicode_literals
import frappe
from   frappe import _

session = frappe.session

def authenticate(user, raise_err = True):
	if session.user == 'Guest':
		if not frappe.db.exists('Chat Token', user):
			if raise_err:
				frappe.throw(_("Sorry, you're not authorized."))
			else:
				return False
		else:
			return True
	else:
		if user != session.user:
			if raise_err:
				frappe.throw(_("Sorry, you're not authorized."))
			else:
				return False
		else:
			return True