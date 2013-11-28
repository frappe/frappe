# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals

import webnotes, os
import webnotes.modules
from webnotes.utils import cstr
from webnotes.modules import export_doc, get_module_path, scrub

def listfolders(path, only_name=0):
	"""
		Returns the list of folders (with paths) in the given path, 
		If only_name is set, it returns only the folder names
	"""

	out = []
	for each in os.listdir(path):
		each = cstr(each)
		dirname = each.split(os.path.sep)[-1]
		fullpath = os.path.join(path, dirname)

		if os.path.isdir(fullpath) and not dirname.startswith('.'):
			out.append(only_name and dirname or fullpath)
	return out

def switch_module(dt, dn, to, frm=None, export=None):
	"""
		Change the module of the given doctype, if export is true, then also export txt and copy
		code files from src
	"""
	webnotes.conn.sql("update `tab"+dt+"` set module=%s where name=%s", (to, dn))

	if export:
		export_doc(dt, dn)

		# copy code files
		if dt in ('DocType', 'Page', 'Report'):
			from_path = os.path.join(get_module_path(frm), scrub(dt), scrub(dn), scrub(dn))
			to_path = os.path.join(get_module_path(to), scrub(dt), scrub(dn), scrub(dn))

			# make dire if exists
			os.system('mkdir -p %s' % os.path.join(get_module_path(to), scrub(dt), scrub(dn)))

			for ext in ('py','js','html','css'):
				os.system('cp %s %s')

def commonify_doclist(doclist, with_comments=1):
	"""
		Makes a doclist more readable by extracting common properties.
		This is used for printing Documents in files
	"""
	from webnotes.utils import get_common_dict, get_diff_dict

	def make_common(doclist):
		c = {}
		if with_comments:
			c['##comment'] = 'These values are common in all dictionaries'
		for k in common_keys:
			c[k] = doclist[0][k]
		return c

	def strip_common_and_idx(d):
		for k in common_keys:
			if k in d: del d[k]
			
		if 'idx' in d: del d['idx']
		return d

	def make_common_dicts(doclist):

		common_dict = {} # one per doctype

		# make common dicts for all records
		for d in doclist:
			if not d['doctype'] in common_dict:
				d1 = d.copy()
				if d1.has_key("name"):
					del d1['name']
				common_dict[d['doctype']] = d1
			else:
				common_dict[d['doctype']] = get_common_dict(common_dict[d['doctype']], d)
		return common_dict

	common_keys = ['owner','docstatus','creation','modified','modified_by']
	common_dict = make_common_dicts(doclist)

	# make docs
	final = []
	for d in doclist:
		f = strip_common_and_idx(get_diff_dict(common_dict[d['doctype']], d))
		f['doctype'] = d['doctype'] # keep doctype!

		# strip name for child records (only an auto generated number!)
		if f['doctype'] != doclist[0]['doctype'] and f.has_key("name"):
			del f['name']

		if with_comments:
			f['##comment'] = d['doctype'] + ('name' in f and (', ' + f['name']) or '')
		final.append(f)

	# add commons
	commons = []
	for d in common_dict.values():
		d['name']='__common__'
		if with_comments:
			d['##comment'] = 'These values are common for all ' + d['doctype']
		commons.append(strip_common_and_idx(d))

	common_values = make_common(doclist)
	return [common_values]+commons+final

def uncommonify_doclist(dl):
	"""
		Expands an commonified doclist
	"""
	# first one has common values
	common_values = dl[0]
	common_dict = webnotes._dict()
	final = []
	idx_dict = {}

	for d in dl[1:]:
		if 'name' in d and d['name']=='__common__':
			# common for a doctype - 
			del d['name']
			common_dict[d['doctype']] = d
		else:
			dt = d['doctype']
			if not dt in idx_dict: idx_dict[dt] = 1;
			d1 = webnotes._dict(common_values.copy())

			# update from common and global
			d1.update(common_dict[dt])
			d1.update(d)

			# idx by sequence
			d1['idx'] = idx_dict[dt]
			
			# increment idx
			idx_dict[dt] += 1

			final.append(d1)

	return final

def pprint_doclist(doclist, with_comments = 1):
	from json import dumps
	return dumps(commonify_doclist(doclist, False), indent=1, sort_keys=True)

def peval_doclist(txt):
	from json import loads
	try:
		return uncommonify_doclist(loads(txt))
	except Exception, e:
		return uncommonify_doclist(eval(txt))
