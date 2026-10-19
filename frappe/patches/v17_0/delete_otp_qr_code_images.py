import frappe


def execute():
	"""Old versions saved OTP App QR codes, which contain the OTP secret, as files in Home/Barcodes."""
	qr_code_images = frappe.get_all(
		"File", {"folder": "Home/Barcodes", "attached_to_doctype": "User"}, pluck="name"
	)
	for name in qr_code_images:
		frappe.delete_doc("File", name, ignore_permissions=True)
