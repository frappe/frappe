# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals, print_function

import frappe
import os
from frappe.utils.file_manager import get_content_hash, get_file, get_file_name
from frappe.utils import get_files_path, get_site_path

# The files missed by the previous patch might have been replaced with new files
# with the same filename
#
# This patch does the following,
# * Detect which files were replaced and rename them with name{hash:5}.extn and
#   update filedata record for the new file
#
# * make missing_files.txt in site dir with files that should be recovered from
#   a backup from a time before version 3 migration
#
# * Patch remaining unpatched File records.
from six import iteritems


def execute():
	frappe.db.auto_commit_on_many_writes = True
	rename_replacing_files()
	for name, file_name, file_url in frappe.db.sql(
			"""select name, file_name, file_url from `tabFile`
			where ifnull(file_name, '')!='' and ifnull(content_hash, '')=''"""):
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
			print('Warning: Error processing ', name)
			b.content_hash = None
		b.flags.ignore_duplicate_entry_error = True
		b.save()
	frappe.db.auto_commit_on_many_writes = False

def get_replaced_files():
	ret = []
	new_files = dict(frappe.db.sql("select name, file_name from `tabFile` where file_name not like 'files/%'"))
	old_files = dict(frappe.db.sql("select name, file_name from `tabFile` where ifnull(content_hash, '')=''"))
	invfiles = invert_dict(new_files)

	for nname, nfilename in iteritems(new_files):
		if 'files/' + nfilename in old_files.values():
			ret.append((nfilename, invfiles[nfilename]))
	return ret

def rename_replacing_files():
	replaced_files = get_replaced_files()
	if len(replaced_files):
		missing_files = [v[0] for v in replaced_files]
		with open(get_site_path('missing_files.txt'), 'w') as f:
			f.write(('\n'.join(missing_files) + '\n').encode('utf-8'))

	for file_name, file_datas in replaced_files:
		print ('processing ' + file_name)
		content_hash = frappe.db.get_value('File', file_datas[0], 'content_hash')
		if not content_hash:
			continue
		new_file_name = get_file_name(file_name, content_hash)
		if os.path.exists(get_files_path(new_file_name)):
			continue
			print('skipping ' + file_name)
		try:
			os.rename(get_files_path(file_name), get_files_path(new_file_name))
		except OSError:
			print('Error renaming ', file_name)
		for name in file_datas:
			f = frappe.get_doc('File', name)
			f.file_name = new_file_name
			f.file_url = '/files/' + new_file_name
			f.save()

def invert_dict(ddict):
	ret = {}
	for k,v in iteritems(ddict):
		if not ret.get(v):
			ret[v] = [k]
		else:
			ret[v].append(k)
	return ret

def get_file_name(fname, hash):
		if '.' in fname:
			partial, extn = fname.rsplit('.', 1)
		else:
			partial = fname
			extn = ''
		return '{partial}{suffix}.{extn}'.format(partial=partial, extn=extn, suffix=hash[:5])
