import frappe
from frappe import _

session = frappe.session


def authenticate(user, raise_err=False):
	unauthenticated = False

	if session.user == 'Guest':
		if not frappe.db.exists('Chat Token', user):
			unauthenticated = True
	elif user != session.user:
		unauthenticated = True

	if unauthenticated:
		if raise_err:
			frappe.throw(_("Sorry, you're not authorized."))
		else:
			return False

	return True
