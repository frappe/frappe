# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json, re
from frappe import _
from frappe.model.document import Document

class Language(Document):
	def validate(self):
		validate_with_regex(self.language_code, "Language Code")

	def before_rename(self, old, new, merge=False):
		validate_with_regex(new, "Name")

def validate_with_regex(name, label):
	pattern = re.compile("^[a-zA-Z]+[-_]*[a-zA-Z]+$")
	if not pattern.match(name):
		frappe.throw(_("""{0} must begin and end with a letter and can only contain letters,
				hyphen or underscore.""").format(label))

def export_languages_json():
	'''Export list of all languages'''
	languages = frappe.db.get_all('Language', fields=['name', 'language_name'])
	languages = [{'name': d.language_name, 'code': d.name} for d in languages]

	languages.sort(key = lambda a: a['code'])

	with open(frappe.get_app_path('frappe', 'geo', 'languages.json'), 'w') as f:
		f.write(frappe.as_json(languages))

def sync_languages():
	'''Sync frappe/geo/languages.json with Language'''
	with open(frappe.get_app_path('frappe', 'geo', 'languages.json'), 'r') as f:
		data = json.loads(f.read())

	for l in data:
		if not frappe.db.exists('Language', l['code']):
			frappe.get_doc({
				'doctype': 'Language',
				'language_code': l['code'],
				'language_name': l['name']
			}).insert()

def update_language_names():
	'''Update frappe/geo/languages.json names (for use via patch)'''
	with open(frappe.get_app_path('frappe', 'geo', 'languages.json'), 'r') as f:
		data = json.loads(f.read())

	for l in data:
		frappe.db.set_value('Language', l['code'], 'language_name', l['name'])