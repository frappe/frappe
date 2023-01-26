import frappe


def execute():
	if "payments" in frappe.get_installed_apps():
		return

	for doctype in (
		"Payment Gateway",
		"Razorpay Settings",
		"Braintree Settings",
		"PayPal Settings",
		"Paytm Settings",
		"Stripe Settings",
	):
		frappe.delete_doc_if_exists("DocType", doctype, force=True)
