# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe
import os
from frappe.utils import get_files_path
from frappe.utils.filemanager import get_content_hash, get_file

def execute():
	for name, file_name, file_url in frappe.db.sql(
			"""select name, file_name, file_url from `tabFile Data`
			where file_name is not null"""):
		b = frappe.bean('File Data', name)
		old_file_name = b.doc.file_name
		b.doc.file_name = os.path.basename(old_file_name)
		if old_file_name.startswith('files/') or old_file_name.startswith('/files/'):
			b.doc.file_url = os.path.normpath('/' + old_file_name)
		else:
			b.doc.file_url = os.path.normpath('/files/' + old_file_name)
		_file_name, content = get_file(file_name)
		b.doc.content_hash = get_content_hash(content)
		b.save()

