import frappe


def execute():
	doctypes = [x.name for x in frappe.get_all("DocType")]
	commit_scheme = frappe.db.auto_commit_on_many_writes
	frappe.db.auto_commit_on_many_writes = 1

	for doctype in doctypes:
		if not frappe.db.table_exists(doctype):
			continue

		docnames_with_whitespaces = frappe.db.sql(
			"SELECT `name` FROM `tab{}`  WHERE CHAR_LENGTH(`name`) !="
			" CHAR_LENGTH(TRIM(`name`))".format(doctype),
			as_dict=True,
		)

		if not docnames_with_whitespaces:
			continue

		for docname in docnames_with_whitespaces:
			docname = docname.name
			new_docname = docname.strip()
			print(
				"Renaming document of `{0}` from `{1}` to `{2}`".format(
					doctype, docname, new_docname
				)
			)
			frappe.rename_doc(doctype, docname, new_docname)

	frappe.db.auto_commit_on_many_writes = commit_scheme
