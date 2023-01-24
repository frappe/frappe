import frappe, json;
from pypika import Criterion
@frappe.whitelist(allow_guest=False)
def image_docfields():
	docfield = frappe.qb.DocType('DocField')
	image_docfields = (
		frappe.qb.from_(docfield)
			.select(docfield.name, docfield.parent, docfield.fieldname, docfield.fieldtype, docfield.label, docfield.options)
			.where((docfield.fieldtype == 'Image') | (docfield.fieldtype == 'Attach Image'))
			.orderby(docfield.parent)
			.distinct()
	).run(as_dict=True)
	return image_docfields;
	