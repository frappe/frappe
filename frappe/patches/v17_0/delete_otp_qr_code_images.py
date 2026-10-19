import frappe


def execute():
	"""Old versions saved OTP App QR codes, which contain the OTP secret, as files in Home/Barcodes."""
	for name in frappe.get_all("File", {"folder": "Home/Barcodes"}, pluck="name"):
		frappe.delete_doc("File", name, ignore_permissions=True)
	frappe.delete_doc("File", "Home/Barcodes", ignore_permissions=True)
