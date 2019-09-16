# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals

import frappe
import re
import redis
import json
import os
from bs4 import BeautifulSoup
from frappe.utils import cint, strip_html_tags
from frappe.model.base_document import get_controller
from six import text_type

def setup_global_tags_table():
	"""
	Creates __global_search table
	:return:
	"""
	frappe.db.create_global_tags_table()


def reset():
	"""
	Deletes all data in __global_tags
	:return:
	"""
	frappe.db.sql('DELETE FROM `__global_tags`')

def delete_global_tags_for_document(doc):
	"""
		Deletes doc entry from __global_tags
	"""
	frappe.db.sql("""DELETE
		FROM `__global_search`
		WHERE doctype = %s
			AND name = %s""", (doc.doctype, doc.name))


def update_global_tags(doc, tags):
	"""
		Adds tags for documents
		:param doc: Document to be added to global tags
	"""
	if frappe.local.conf.get('disable_global_tags') or not doc.get("_user_tags"):
		return

	value = {
		"doctype": doc.doctype,
		"name": doc.name,
		"title": (doc.get_title() or '')[:int(frappe.db.VARCHAR_LEN)],
		"tags": tags.lower()
	}

	frappe.db.multisql({
		'mariadb': '''INSERT INTO `__global_tags`
			(`doctype`, `name`, `title`, `tags`)
			VALUES (%(doctype)s, %(name)s, %(title)s, %(tags)s)
			ON DUPLICATE key UPDATE
				`tags`=%(tags)s
		''',
		'postgres': '''INSERT INTO `__global_tags`
			(`doctype`, `name`, `title`, `tags`)
			VALUES (%(doctype)s, %(name)s, %(title)s, %(tags)s)
			ON CONFLICT("doctype", "name") DO UPDATE SET
				`tags`=%(tags)s
		'''
	}, value)

def delete_for_document(doc):
	"""
		Delete the __global_tags entry of a document that has
		been deleted
		:param doc: Deleted document
	"""

	frappe.db.sql('''DELETE
		FROM `__global_tags`
		WHERE doctype = %s
		AND name = %s''', (doc.doctype, doc.name))

@frappe.whitelist()
def get_documents_for_tag(tag):
	"""
	Search for given text in __global_tags
	:param tag: tag to be searched
	"""
	# remove hastag # from tag
	results = {}
	tag = tag[1:]

	mariadb_fields = '`doctype`, `name`, `title`, `tags`, MATCH(`tags`) AGAINST ({} IN BOOLEAN MODE) AS rank'.format(frappe.db.escape('+' + tag + '*'))
	postgres_fields = '`doctype`, `name`, `title`, `tags`, TO_TSVECTOR("tags") @@ PLAINTO_TSQUERY({}) AS rank'.format(frappe.db.escape(tag))

	common_query = '''SELECT {fields} FROM `__global_tags`'''

	result = frappe.db.multisql({
			'mariadb': common_query.format(fields=mariadb_fields),
			'postgres': common_query.format(fields=postgres_fields)
		}, as_dict=True)

	for res in result:
		if res.doctype in results.keys():
			results[res.doctype].append(res)
		else:
			results[res.doctype] = [res]

	return results