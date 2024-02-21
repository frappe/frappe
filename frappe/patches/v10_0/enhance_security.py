import frappe
from frappe.utils import cint


def execute():
	"""
	The motive of this patch is to increase the overall security in frappe framework

	Existing passwords won't be affected, however, newly created accounts
	will have to adheare to the new password policy guidelines. Once can always
	loosen up the security by modifying the values in System Settings, however,
	we strongly advice against doing so!

	Security is something we take very seriously at frappe,
	and hence we chose to make security tighter by default.
	"""
	doc = frappe.get_single("System Settings")

	# Enforce a Password Policy
	if cint(doc.enable_password_policy) == 0:
		doc.enable_password_policy = 1

	# Enforce a password score as calculated by zxcvbn
	if cint(doc.minimum_password_score) <= 2:
		doc.minimum_password_score = 2

	# Disallow more than 3 consecutive login attempts in a span of 60 seconds
	if cint(doc.allow_consecutive_login_attempts) <= 3:
		doc.allow_consecutive_login_attempts = 3

	doc.flags.ignore_mandatory = True
	doc.save()
