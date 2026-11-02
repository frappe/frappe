import re

import frappe


def execute():
	"""Old versions saved OTP App QR codes, which contain the OTP secret, as files in Home/Barcodes."""
	files = frappe.get_all(
		"File", {"folder": "Home/Barcodes", "attached_to_doctype": "User"}, ["name", "file_name"]
	)
	for file in files:
		if re.fullmatch(r"[0-9a-f]{20}\.png", file.file_name):
			frappe.delete_doc("File", file.name, ignore_permissions=True)
