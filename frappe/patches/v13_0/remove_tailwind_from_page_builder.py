# Copyright (c) 2020, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import nts


def execute():
	nts.reload_doc("website", "doctype", "web_page_block")
	# remove unused templates
	nts.delete_doc("Web Template", "Navbar with Links on Right", force=1)
	nts.delete_doc("Web Template", "Footer Horizontal", force=1)
