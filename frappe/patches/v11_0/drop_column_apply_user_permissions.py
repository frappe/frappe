import nts


def execute():
	column = "apply_user_permissions"
	to_remove = ["DocPerm", "Custom DocPerm"]

	for doctype in to_remove:
		if nts.db.table_exists(doctype):
			if column in nts.db.get_table_columns(doctype):
				nts.db.sql(f"alter table `tab{doctype}` drop column {column}")

	nts.reload_doc("core", "doctype", "docperm", force=True)
	nts.reload_doc("core", "doctype", "custom_docperm", force=True)
