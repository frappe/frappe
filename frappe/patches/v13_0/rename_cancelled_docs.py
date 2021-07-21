import frappe
from frappe.model.naming import NameParser
from frappe.model.rename_doc import rename_doc

def execute():
	"""Rename already cancelled documents by adding `CAN-X` postfix instead of `-X`.
	"""
	for doctype in frappe.db.get_all('DocType'):
		doctype = frappe.get_doc('DocType', doctype.name)
		if doctype.is_submittable and frappe.db.table_exists(doctype.name):
			cancelled_docs = frappe.db.get_all(doctype.name, ['amended_from', 'name'], {'docstatus':2})

			for doc in cancelled_docs:
				if '-CAN-' in doc.name:
					continue

				current_name = doc.name

				if getattr(doc, "amended_from", None):
					orig_name, counter = NameParser.parse_docname(doc.name)
				else:
					orig_name, counter = doc.name, 0
				new_name = f'{orig_name}-CAN-{counter or 0}'

				print(f"Renaming {doctype.name} record from {current_name} to {new_name}")
				rename_doc(doctype.name, current_name, new_name, ignore_permissions=True, show_alert=False)
	frappe.db.commit()
