import nts


def execute():
	nts.reload_doc("core", "doctype", "doctype_link")
	nts.reload_doc("core", "doctype", "doctype_action")
	nts.reload_doc("core", "doctype", "doctype")
	nts.model.delete_fields({"DocType": ["hide_heading", "image_view", "read_only_onload"]}, delete=1)

	nts.db.delete("Property Setter", {"property": "read_only_onload"})
