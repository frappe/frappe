import frappe, json 

@frappe.whitelist()
def get_in_list_view_fields(doctype):
	meta = frappe.get_meta(doctype)
	fields = []

	if meta.title_field:
		fields.append(meta.title_field)
	else:
		fields.append('name')

	if meta.has_field('status'):
		fields.append('status')

	fields += [df.fieldname for df in meta.fields if df.in_list_view and df.fieldname not in fields]

	def get_field_df(fieldname):
		if fieldname == 'name':
			return { 'label': 'Name', 'fieldname': 'name', 'fieldtype': 'Data' }
		return meta.get_field(fieldname).as_dict()

	return [get_field_df(f) for f in fields]


@frappe.whitelist()
def delete_multiple(web_form_name, docnames):
	web_form = frappe.get_doc("Web Form", web_form_name)

	docnames = json.loads(docnames)

	allowed_docnames = []
	restricted_docnames = []

	for docname in docnames:
		owner = frappe.db.get_value(web_form.doc_type, docname, "owner")
		if frappe.session.user == owner and web_form.allow_delete:
			allowed_docnames.append(docname)
		else:
			restricted_docnames.append(docname)

	for docname in allowed_docnames:
		frappe.delete_doc(web_form.doc_type, docname, ignore_permissions=True)

	if restricted_docnames:
		raise frappe.PermissionError("You do not have permisssion to delete " + ", ".join(restricted_docnames))