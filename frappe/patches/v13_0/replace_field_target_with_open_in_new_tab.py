import nts


def execute():
	doctype = "Top Bar Item"
	if not nts.db.table_exists(doctype) or not nts.db.has_column(doctype, "target"):
		return

	nts.reload_doc("website", "doctype", "top_bar_item")
	nts.db.set_value(doctype, {"target": 'target = "_blank"'}, "open_in_new_tab", 1)
