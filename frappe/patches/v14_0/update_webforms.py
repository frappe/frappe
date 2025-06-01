# Copyright (c) 2021, nts Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt


import nts


def execute():
	nts.reload_doc("website", "doctype", "web_form_list_column")
	nts.reload_doctype("Web Form")

	for web_form in nts.get_all("Web Form", fields=["*"]):
		if web_form.allow_multiple and not web_form.show_list:
			nts.db.set_value("Web Form", web_form.name, "show_list", True)
