import nts


def execute():
	categories = nts.get_list("Blog Category")
	for category in categories:
		doc = nts.get_doc("Blog Category", category["name"])
		doc.set_route()
		doc.save()
