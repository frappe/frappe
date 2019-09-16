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

def setup_global_search_table():
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

def sync_value_in_queue(value):
	try:
		# append to search queue if connected
		frappe.cache().lpush('global_tags_queue', json.dumps(value))
	except redis.exceptions.ConnectionError:
		# not connected, sync directly
		sync_value(value)

def sync_global_tags():
	"""
		Inserts / updates values from `global_tags_queue` to __global_tags.
		This is called via job scheduler
		:param flags:
		:return:
	"""
	while frappe.cache().llen('global_tags_queue') > 0:
		value = json.loads(frappe.cache().lpop('global_tags_queue').decode('utf-8'))
		sync_value(value)

def delete_global_tags_records_for_document_with_tag(doctype, docname, tag):
	frappe.db.sql('''
		DELETE
		FROM `__global_search`
		WHERE doctype = %s
			AND name = %s
			AND tag = %s''', (doctype, docname, tag))

def sync_value(value):
	'''
		Sync a given document to global tags
		:param value: dict of { doctype, name, title, tag }
	'''

	frappe.db.multisql({
		'mariadb': '''INSERT INTO `__global_tags`
			(`doctype`, `name`, `title`, `tag`)
			VALUES (%(doctype)s, %(name)s, %(title)s, %(tag)s)
		''',
		'postgres': '''INSERT INTO `__global_search`
			(`doctype`, `name`, `title`, `tag`)
			VALUES (%(doctype)s, %(name)s, %(title)s, %(tag)s)
		'''
	}, value)

def update_global_tags(doc):
	"""
		Adds tags for documents
		:param doc: Document to be added to global tags
	"""
	if frappe.local.conf.get('disable_global_tags'):
		return

	values = {
		"doctype": doc.doctype,
		"name": doc.name,
		"title": (doc.get_title() or '')[:int(frappe.db.VARCHAR_LEN)],
		"tag": "tag"
	}

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