import frappe

def execute():
	frappe.delete_doc_if_exists("DocType", "Tag Category")
	frappe.delete_doc_if_exists("DocType", "Tag Doc Category")

	frappe.reload_doc("desk", "doctype", "tag")

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

				tag_list.append(tag.strip())

				tag_link_name = frappe.generate_hash(dt_tags.name + tag.strip(), 10),
				tag_links.append((tag_link_name, doctype.name, dt_tags.name, tag.strip(), time, time, 'Administrator'))


	temp_list = []
	for count, value in enumerate(set(tag_list)):
		temp_list.append((value, time, time, 'Administrator'))

		if count and (count%1000 == 0 or count == len(tag_list)-1):
			frappe.db.sql("""
				INSERT INTO `tabTag` (`name`, `creation`, `modified`, `modified_by`) VALUES {}
			""".format(", ".join(['%s'] * len(temp_list))), tuple(temp_list))
			temp_list = []

	for count, value in enumerate(set(tag_links)):
		temp_list.append(value)

		if count and (count%1000 == 0 or count == len(tag_links)-1):
			frappe.db.sql("""
				INSERT INTO `tabTag Link` (`name`, `dt`, `dn`, `tag`, `creation`, `modified`, `modified_by`) VALUES {}
			""".format(", ".join(['%s'] * len(temp_list))), tuple(temp_list))
			temp_list = []