import frappe

def execute():
	frappe.delete_doc_if_exists("DocType", "Tag Category")
	frappe.delete_doc_if_exists("DocType", "Tag Doc Category")

	frappe.reload_doc("desk", "doctype", "tag")
	frappe.reload_doc("desk", "doctype", "tag_link")

	time = frappe.utils.get_datetime()
	frappe.db.auto_commit_on_many_writes = True

	for doctype in frappe.get_list("DocType", filters={"istable": 0, "issingle": 0}):
		if not (frappe.db.count(doctype.name) or frappe.db.has_column(doctype.name, "_user_tags")):
			continue

		for _user_tags in frappe.db.sql("select `name`, `_user_tags` from `tab{0}`".format(doctype.name), as_dict=True):
			if not _user_tags.get("_user_tags"):
				continue

			for tag in _user_tags.get("_user_tags").split(",") if _user_tags.get("_user_tags") else []:
				if not tag:
					continue

				tag_name = frappe.db.escape(tag.strip())
				tag_link_name = frappe.generate_hash(_user_tags.name + tag.strip() + doctype.name, 10)

				insert_tag(tag_name, time, time, "Administrator")
				insert_tag_link(tag_link_name, doctype.name, _user_tags.name, tag_name, time, time, "Administrator")

	if frappe.db.auto_commit_on_many_writes:
		frappe.db.auto_commit_on_many_writes = False

def insert_tag(name, creation, modified, modified_by):
	if frappe.db.exists("Tag", name):
		return

	doc = frappe.new_doc("Tag")
	doc.name = name
	doc.creation = creation
	doc.modified = modified
	doc.modified_by = modified_by
	doc.db_insert()

def insert_tag_link(name, document_type, document_name, tag, creation, modified, modified_by):
	if frappe.db.exists("Tag", {"document_type": document_type, "document_name": document_name, "tag": tag}):
		return

	doc = frappe.new_doc("Tag Link")
	doc.name = name
	doc.document_type = document_type
	doc.document_name = document_name
	doc.tag = tag
	doc.parenttype = document_type
	doc.parent = document_name
	doc.creation = creation
	doc.modified = modified
	doc.modified_by = modified_by
	doc.db_insert()