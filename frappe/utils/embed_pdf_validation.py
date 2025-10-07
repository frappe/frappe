"""
EmbedPdf field validation utilities
"""

import mimetypes
import os

import frappe


def validate_pdf_file(file_path):
	"""
	Validate that the uploaded file is a PDF

	Args:
	    file_path (str): Path to the uploaded file

	Raises:
	    frappe.ValidationError: If file is not a PDF
	"""
	if not file_path:
		return

	# Check file extension
	filename = os.path.basename(file_path)
	if not filename.lower().endswith(".pdf"):
		frappe.throw(frappe._("Only PDF files are allowed for EmbedPdf field type."))

	# Check MIME type if possible
	mime_type, _mime_encoding = mimetypes.guess_type(file_path)
	if mime_type and mime_type != "application/pdf":
		frappe.throw(frappe._("File must be of type PDF (application/pdf)."))


@frappe.whitelist()
def validate_embed_pdf_field(doctype, fieldname, file_url):
	"""
	Server-side validation for EmbedPdf field

	Args:
	    doctype (str): Document type
	    fieldname (str): Field name
	    file_url (str): Uploaded file URL

	Returns:
	    dict: Validation result
	"""
	try:
		if not file_url:
			return {"valid": True}

		# Basic URL validation for PDF
		if not file_url.lower().endswith(".pdf"):
			return {
				"valid": False,
				"message": frappe._("Only PDF files are allowed for EmbedPdf field type."),
			}

		# Additional validation can be added here
		# For example, checking file size, scanning for malware, etc.

		return {"valid": True}

	except Exception as e:
		frappe.log_error(
			f"EmbedPdf validation error for Doctype: {doctype}, Field: {fieldname}, Error: {e!s}"
		)
		return {"valid": False, "message": frappe._("Error validating PDF file.")}
