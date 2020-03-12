# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import strip_html_tags, is_html
from frappe.integrations.utils import make_post_request
import json

class Translation(Document):
	def validate(self):
		if is_html(self.source_text):
			self.remove_html_from_source()

	def remove_html_from_source(self):
		self.source_text = strip_html_tags(self.source_text).strip()

	def on_update(self):
		clear_user_translation_cache(self.language)

	def on_trash(self):
		clear_user_translation_cache(self.language)

	def contribute(self):
		pass

	def get_contribution_status(self):
		pass

@frappe.whitelist()
def create_translations(translation_map, language):
	from frappe.frappeclient import FrappeClient

	translation_map_str = translation_map
	translation_map = json.loads(translation_map_str)

	# first create / update local user translations
	for source_id, translation_dict in translation_map.items():
		translation_dict = frappe._dict(translation_dict)
		existing_doc_name = frappe.db.exists('Translation', {
			'source_text': translation_dict.source_text,
			'context': translation_dict.context,
			'language': language,
		})
		if existing_doc_name:
			frappe.set_values('Translation', existing_doc_name, {
				'translated_text': translation_dict.translated_text,
				'contributed': 1,
				'contribution_status': 'Pending'
			})
		else:
			doc = frappe.get_doc({
				'doctype': 'Translation',
				'source_text': translation_dict.source_text,
				'contributed': 1,
				'contribution_status': 'Pending',
				'translated_text': translation_dict.translated_text,
				'context': translation_dict.context,
				'language': language
			})
			doc.insert()

	params = {
		'language': language,
		'contributor_email': frappe.session.user,
		'contributor_name': frappe.utils.get_fullname(frappe.session.user),
		'translation_map': translation_map_str
	}

	translator = FrappeClient(frappe.conf.translator_url)
	return translator.post_api('translator.api.add_translations', params=params)

def clear_user_translation_cache(lang):
	frappe.cache().hdel('lang_user_translations', lang)