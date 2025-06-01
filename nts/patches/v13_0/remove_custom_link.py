import nts


def execute():
	"""
	Remove the doctype "Custom Link" that was used to add Custom Links to the
	Dashboard since this is now managed by Customize Form.
	Update `parent` property to the DocType and delte the doctype
	"""
	nts.reload_doctype("DocType Link")
	if nts.db.has_table("Custom Link"):
		for custom_link in nts.get_all("Custom Link", ["name", "document_type"]):
			nts.db.sql(
				"update `tabDocType Link` set custom=1, parent=%s where parent=%s",
				(custom_link.document_type, custom_link.name),
			)

		nts.delete_doc("DocType", "Custom Link")
