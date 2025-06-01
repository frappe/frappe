import nts


def execute():
	for name in ("desktop", "space"):
		nts.delete_doc("Page", name)
