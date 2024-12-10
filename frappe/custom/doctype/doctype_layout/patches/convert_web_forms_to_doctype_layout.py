import frappe


def execute():
	for web_form_name in frappe.get_all("Web Form", pluck="name"):
		web_form = frappe.get_doc("Web Form", web_form_name)
		doctype_layout = frappe.get_doc(
<<<<<<< HEAD
			dict(
				doctype="DocType Layout",
				document_type=web_form.doc_type,
				name=web_form.title,
				route=web_form.route,
				fields=[
					dict(fieldname=d.fieldname, label=d.label)
					for d in web_form.web_form_fields
					if d.fieldname
				],
			)
=======
			doctype="DocType Layout",
			document_type=web_form.doc_type,
			name=web_form.title,
			route=web_form.route,
			fields=[
				dict(fieldname=d.fieldname, label=d.label) for d in web_form.web_form_fields if d.fieldname
			],
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
		).insert()
		print(doctype_layout.name)
