import nts


def execute():
	item = nts.db.exists("Navbar Item", {"item_label": "Background Jobs"})
	if not item:
		return

	nts.delete_doc("Navbar Item", item)
