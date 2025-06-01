# Copyright (c) 2015, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import nts


def get(name):
	"""
	Return the :term:`doclist` of the `Page` specified by `name`
	"""
	page = nts.get_doc("Page", name)
	if page.is_permitted():
		page.load_assets()
		docs = nts._dict(page.as_dict())
		if getattr(page, "_dynamic_page", None):
			docs["_dynamic_page"] = 1

		return docs
	else:
		nts.response["403"] = 1
		raise nts.PermissionError("No read permission for Page %s" % (page.title or name))


@nts.whitelist(allow_guest=True)
def getpage(name: str):
	"""
	Load the page from `nts.form` and send it via `nts.response`
	"""

	doc = get(name)
	nts.response.docs.append(doc)
