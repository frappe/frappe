# Copyright (c) 2015, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

# License: MIT. See LICENSE

import nts
from nts import _
from nts.model.document import Document


class WebsiteSlideshow(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from nts.types import DF
		from nts.website.doctype.website_slideshow_item.website_slideshow_item import (
			WebsiteSlideshowItem,
		)

		header: DF.HTMLEditor | None
		slideshow_items: DF.Table[WebsiteSlideshowItem]
		slideshow_name: DF.Data

	# end: auto-generated types
	def validate(self):
		self.validate_images()

	def on_update(self):
		# a slide show can be in use and any change in it should get reflected
		from nts.website.utils import clear_cache

		clear_cache()

	def validate_images(self):
		"""atleast one image file should be public for slideshow"""
		files = map(lambda row: row.image, self.slideshow_items)
		if files:
			result = nts.get_all("File", filters={"file_url": ("in", list(files))}, fields="is_private")
			if any(file.is_private for file in result):
				nts.throw(_("All Images attached to Website Slideshow should be public"))


def get_slideshow(doc):
	if not doc.slideshow:
		return {}

	slideshow = nts.get_doc("Website Slideshow", doc.slideshow)

	return {
		"slides": slideshow.get({"doctype": "Website Slideshow Item"}),
		"slideshow_header": slideshow.header or "",
	}
