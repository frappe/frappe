# Copyright (c) 2020, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import nts


def execute():
	"""Set default module for standard Web Template, if none."""
	nts.reload_doc("website", "doctype", "Web Template Field")
	nts.reload_doc("website", "doctype", "web_template")

	standard_templates = nts.get_list("Web Template", {"standard": 1})
	for template in standard_templates:
		doc = nts.get_doc("Web Template", template.name)
		if not doc.module:
			doc.module = "Website"
			doc.save()
