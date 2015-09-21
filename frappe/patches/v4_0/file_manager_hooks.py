# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe
import os
from frappe.utils import get_files_path
from frappe.utils.file_manager import get_content_hash, get_file


def execute():
	frappe.reload_doc('core', 'doctype', 'file_data')
	for name, file_name, file_url in frappe.db.sql(
			"""select name, file_name, file_url from `tabFile`
			where file_name is not null"""):
		b = frappe.get_doc('File', name)
		old_file_name = b.file_name
		b.file_name = os.path.basename(old_file_name)
		if old_file_name.startswith('files/') or old_file_name.startswith('/files/'):
			b.file_url = os.path.normpath('/' + old_file_name)
		else:
			b.file_url = os.path.normpath('/files/' + old_file_name)
		try:
			_file_name, content = get_file(name)
			b.content_hash = get_content_hash(content)
		except IOError:
			print 'Warning: Error processing ', name
			_file_name = old_file_name
			b.content_hash = None

		try:
			b.save()
		except frappe.DuplicateEntryError:
			frappe.delete_doc(b.doctype, b.name)

