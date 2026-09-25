# Copyright (c) 2015, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document
from frappe.translate import MERGED_TRANSLATION_KEY, USER_TRANSLATION_KEY
from frappe.utils import sanitize_html


class Translation(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		context: DF.Data | None
		contributed: DF.Check
		contribution_docname: DF.Data | None
		contribution_status: DF.Literal["", "Pending", "Verified", "Rejected"]
		language: DF.Link
		source_text: DF.Code
		translated_text: DF.Code

	# end: auto-generated types
	def validate(self):
		self.translated_text = sanitize_html(self.translated_text)

	def on_update(self):
		clear_user_translation_cache(self.language)
		if self.has_value_changed("language") and (doc_before_save := self.get_doc_before_save()):
			clear_user_translation_cache(doc_before_save.language)

	def on_trash(self):
		clear_user_translation_cache(self.language)


def clear_user_translation_cache(lang):
	frappe.cache.hdel(USER_TRANSLATION_KEY, lang)
	frappe.cache.hdel(MERGED_TRANSLATION_KEY, lang)
