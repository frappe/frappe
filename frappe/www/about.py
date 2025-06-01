# Copyright (c) 2015, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import nts

sitemap = 1


def get_context(context):
	context.doc = nts.get_cached_doc("About Us Settings")

	return context
