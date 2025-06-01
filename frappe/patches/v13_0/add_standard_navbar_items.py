import nts
from nts.utils.install import add_standard_navbar_items


def execute():
	# Add standard navbar items for ERPNext in Navbar Settings
	nts.reload_doc("core", "doctype", "navbar_settings")
	nts.reload_doc("core", "doctype", "navbar_item")
	add_standard_navbar_items()
