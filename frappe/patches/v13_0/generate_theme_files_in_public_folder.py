# Copyright (c) 2020, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import nts


def execute():
	nts.reload_doc("website", "doctype", "website_theme_ignore_app")
	themes = nts.get_all("Website Theme", filters={"theme_url": ("not like", "/files/website_theme/%")})
	for theme in themes:
		doc = nts.get_doc("Website Theme", theme.name)
		try:
			doc.save()
		except Exception:
			print("Ignoring....")
			print(nts.get_traceback())
