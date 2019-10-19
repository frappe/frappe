import frappe

def execute():
	frappe.delete_doc_if_exists("DocType", "Tag Category")
	frappe.delete_doc_if_exists("DocType", "Tag Doc Category")

	frappe.reload_doc("desk", "doctype", "tag")
	frappe.reload_doc("desk", "doctype", "tag_link")

	tag_list = []
	tag_links = []
	time = frappe.utils.get_datetime()

	for doctype in frappe.get_list("DocType", filters={"istable": 0, "issingle": 0}):
		for dt_tags in frappe.db.sql("select `name`, `_user_tags` from `tab{0}`".format(doctype.name), as_dict=True):
			tags = dt_tags.get("_user_tags").split(",") if dt_tags.get("_user_tags") else None
			if not tags:
				continue

			for tag in tags:
				if not tag:
					continue

				tag_list.append((tag.strip(), time, time, 'Administrator'))

				tag_link_name = frappe.generate_hash(dt_tags.name + tag.strip() + doctype.name, 10),
				tag_links.append((tag_link_name, doctype.name, dt_tags.name, tag.strip(), time, time, 'Administrator'))

	frappe.db.bulk_insert("Tag", fields=["name", "creation", "modified", "modified_by"], values=set(tag_list))
	frappe.db.bulk_insert("Tag Link", fields=["name", "document_type", "document_name", "tag", "creation", "modified", "modified_by"], values=set(tag_links))