# Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
# 
# MIT License (MIT)
# 
# Permission is hereby granted, free of charge, to any person obtaining a 
# copy of this software and associated documentation files (the "Software"), 
# to deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the 
# Software is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in 
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
# CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
# OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#

# TODO:
# Patch: Remove DocFormat

# imports
import webnotes
import webnotes.model
import webnotes.model.doc
from webnotes.utils.cache import CacheItem

class _DocType:
	"""
	   The _DocType object is created internally using the module's `get` method.
	"""
	def __init__(self, name):
		self.name = name

	def make_doclist(self, form=1):
		"""

		"""
		# do not load from cache if auto cache clear is enabled
		import conf
		from_cache = True
		if hasattr(conf, 'auto_cache_clear'):
			from_cache = not conf.auto_cache_clear
		
		if form and from_cache:
			cached_doclist = self.load_from_cache()
			if cached_doclist: return cached_doclist

		# Get parent doc and its fields
		doclist = webnotes.model.doc.get('DocType', self.name, 1)
		doclist += self.get_custom_fields(self.name)

		if form:
			table_fields = [t[0] for t in self.get_table_fields(doclist)]
			# for each unique table
			for t in list(set(table_fields)):
				# Get child doc and its fields
				table_doclist = webnotes.model.doc.get('DocType', t, 1)
				table_doclist += self.get_custom_fields(t)
				doclist += table_doclist

		self.apply_property_setters(doclist)
		
		if form:
			self.load_select_options(doclist)
			self.add_code(doclist[0])
			self.load_print_formats(doclist)
			self.insert_into_cache(doclist)

		return doclist

	def get_custom_fields(self, doc_type):
		"""
			Gets a list of custom field docs masked as type DocField
		"""
		custom_doclist = []
		res = webnotes.conn.sql("""SELECT * FROM `tabCustom Field`
			WHERE dt = %s AND docstatus < 2""", doc_type, as_dict=1)
		for r in res:
			# Cheat! Mask Custom Field as DocField
			custom_field = webnotes.model.doc.Document(fielddata=r)
			self.mask_custom_field(custom_field, doc_type)
			custom_doclist.append(custom_field)

		return custom_doclist

	def mask_custom_field(self, custom_field, doc_type):
		"""
			Masks doctype and parent related properties of Custom Field as that
			of DocField
		"""
		custom_field.fields.update({
			'doctype': 'DocField',
			'parent': doc_type,
			'parentfield': 'fields',
			'parenttype': 'DocType',
		})

	def get_table_fields(self, doclist):
		"""
			Returns [[options, fieldname]] of fields of type 'Table'
		"""
		table_fields = []
		for d in doclist:
			if d.doctype=='DocField' and d.fieldtype == 'Table':
				table_fields.append([d.options, d.fieldname])
		return table_fields

	def apply_property_setters(self, doclist):
		"""

		"""
		property_dict, doc_type_list = self.get_property_setters(doclist)
		for d in doclist:
			self.update_field_properties(d, property_dict)
		
		self.apply_previous_field_properties(doclist, property_dict,
				doc_type_list)

	def get_property_setters(self, doclist):
		"""
			Returns a dict of property setter lists and doc_type_list
		"""
		from webnotes.utils import cstr
		property_dict = {}
		# final property dict will be
		# {
		#	doc_type: {
		#		fieldname: [list of property setter dicts]
		#	}
		# }

		doc_type_list = list(set(
			d.doctype=='DocType' and d.name or d.parent
			for d in doclist))
		in_string = '", "'.join(doc_type_list)
		for ps in webnotes.conn.sql("""\
			SELECT doc_type, field_name, property, property_type, value
			FROM `tabProperty Setter`
			WHERE doc_type IN ("%s")""" % in_string, as_dict=1):
			property_dict.setdefault(ps.get('doc_type'),
					{}).setdefault(cstr(ps.get('field_name')), []).append(ps)

		return property_dict, doc_type_list

	def update_field_properties(self, d, property_dict):
		"""
			apply properties except previous_field ones
		"""
		from webnotes.utils import cstr
		# get property setters for a given doctype's fields
		doctype_property_dict = (d.doctype=='DocField' and property_dict.get(d.parent) or
			property_dict.get(d.name))
		if not (doctype_property_dict and doctype_property_dict.get(cstr(d.fieldname))): return
		
		from webnotes.utils import cint
		prop_updates = []
		for prop in doctype_property_dict.get(cstr(d.fieldname)):
			if prop.get('property')=='previous_field': continue
			if prop.get('property_type') == 'Check' or \
					prop.get('value') in ['0', '1']:
				prop_updates.append([prop.get('property'), cint(prop.get('value'))])
			else:
				prop_updates.append([prop.get('property'), prop.get('value')])

		prop_updates and d.fields.update(dict(prop_updates))

	def apply_previous_field_properties(self, doclist, property_dict,
			doc_type_list):
		"""

		"""
		prev_field_dict = self.get_previous_field_properties(property_dict)
		if not prev_field_dict: return

		for doc_type in doc_type_list:
			docfields = self.get_sorted_docfields(doclist, doc_type)
			docfields = self.sort_docfields(doc_type, docfields, prev_field_dict)
			if docfields: self.change_idx(doclist, docfields, doc_type)

	def get_previous_field_properties(self, property_dict):
		"""
			setup prev_field_dict
		"""
		from webnotes.utils import cstr
		doctype_prev_field_list = []
		for doc_type in property_dict:
			prev_field_list = []
			for prop_list in property_dict.get(doc_type).values():
				for prop in prop_list:
					if prop.get('property') == 'previous_field':
						prev_field_list.append([prop.get('value'),
							prop.get('field_name')])
						break
			if not prev_field_list: continue
			doctype_prev_field_list.append([doc_type, dict(prev_field_list)])
		if not doctype_prev_field_list: return
		return dict(doctype_prev_field_list)

	def get_sorted_docfields(self, doclist, doc_type):
		"""
			get a sorted list of docfield names
		"""
		sorted_list = sorted([
				d for d in doclist
				if d.doctype == 'DocField'
				and d.parent == doc_type
			], key=lambda df: df.idx)
		return [d.fieldname for d in sorted_list]

	def sort_docfields(self, doc_type, docfields, prev_field_dict):
		"""
			
		"""
		temp_dict = prev_field_dict.get(doc_type)
		if not temp_dict: return

		prev_field = 'None' in temp_dict and 'None' or docfields[0]
		i = 0
		while temp_dict:
			get_next_docfield = True
			cur_field = temp_dict.get(prev_field)
			if cur_field and cur_field in docfields:
				try:
					del temp_dict[prev_field]
					if prev_field in docfields:
						docfields.remove(cur_field)
						docfields.insert(docfields.index(prev_field) + 1,
								cur_field)
					elif prev_field == 'None':
						docfields.remove(cur_field)
						docfields.insert(0, cur_field)
				except ValueError:
					pass

				if cur_field in temp_dict:
					prev_field = cur_field
					get_next_docfield = False

			if get_next_docfield:
				i += 1
				if i>=len(docfields): break
				prev_field = docfields[i]
				keys, vals = temp_dict.keys(), temp_dict.values()
				if prev_field in vals:
					i -= 1
					prev_field = keys[vals.index(prev_field)]
		
		return docfields

	def change_idx(self, doclist, docfields, doc_type):
		for d in doclist:
			if d.fieldname and d.fieldname in docfields and d.parent == doc_type:
				d.idx = docfields.index(d.fieldname) + 1
				
	def add_code(self, doc):
		"""add js, css code"""
		import os
		from webnotes.modules import scrub, get_module_path
		import conf
		
		modules_path = get_module_path(doc.module)

		path = os.path.join(modules_path, 'doctype', scrub(doc.name))

		def _add_code(fname, fieldname):
			fpath = os.path.join(path, fname)
			if os.path.exists(fpath):
				with open(fpath, 'r') as f:
					doc.fields[fieldname] = f.read()
			
		_add_code(scrub(doc.name) + '.js', '__js')
		_add_code(scrub(doc.name) + '.css', '__css')
		_add_code('%s_list.js' % scrub(doc.name), '__listjs')
		_add_code('help.md', 'description')
		
		# embed all require files
		import re
		def _sub(match):
			fpath = os.path.join(os.path.dirname(conf.modules_path), \
				re.search('["\'][^"\']*["\']', match.group(0)).group(0)[1:-1])
			if os.path.exists(fpath):
				with open(fpath, 'r') as f:
					return '\n' + f.read() + '\n'
			else:
				return '\n// no file "%s" found \n' % fpath
		
		if doc.fields.get('__js'):
			doc.fields['__js'] = re.sub('(wn.require\([^\)]*.)', _sub, doc.fields['__js'])
		
		# custom script
		from webnotes.model.code import get_custom_script
		custom = get_custom_script(doc.name, 'Client') or ''
		doc.fields['__js'] = doc.fields.setdefault('__js', '') + '\n' + custom
		

	def load_select_options(self, doclist):
		"""
			Loads Select options for 'Select' fields
			with link: as start of options
		"""
		for d in doclist:
			if (d.doctype == 'DocField' and d.fieldtype == 'Select' and
				d.options and d.options[:5].lower() == 'link:'):
				
				# Get various options
				opt_list = self._get_select_options(d)

				opt_list = [''] + [o[0] or '' for o in opt_list]
				d.options = "\n".join(opt_list)

	def _get_select_options(self, d):
		"""
			Queries and returns select options
			(called by load_select_options)
		"""
		op = d.options.split('\n')
		if len(op) > 1 and op[1][:4].lower() == 'sql:':
			# Execute the sql query
			query = op[1][4:].replace('__user',
						webnotes.session.get('user'))
		else:
			# Extract DocType and Conditions
			# and execute the resulting query
			dt = op[0][5:].strip()
			cond_list = [cond.replace('__user',
				webnotes.session.get('user')) for cond in op[1:]]
			query = """\
				SELECT name FROM `tab%s`
				WHERE %s docstatus!=2
				ORDER BY name ASC""" % (dt,
				cond_list and (" AND ".join(cond_list) + " AND ") or "")
		try:
			opt_list = webnotes.conn.sql(query)
		except:
			# WARNING: Exception suppressed
			opt_list = []

		return opt_list

	def load_print_formats(self, doclist):
		"""
			Load Print Formats in doclist
		"""
		# TODO: Process Print Formats for $import
		# to deprecate code in print_format.py
		# if this is implemented, clear CacheItem on saving print format
		print_formats = webnotes.conn.sql("""\
			SELECT * FROM `tabPrint Format`
			WHERE doc_type=%s AND docstatus<2""", doclist[0].fields.get('name'),
			as_dict=1)
		for pf in print_formats:
			if not pf: continue
			print_format_doc = webnotes.model.doc.Document('Print Format', fielddata=pf)
			doclist.append(print_format_doc)

	def load_from_cache(self):
		import json
		json_doclist = CacheItem(self.name).get()
		if json_doclist:
			return [webnotes.model.doc.Document(fielddata=d)
					for d in json.loads(json_doclist)]

	def insert_into_cache(self, doclist):
		import json
		json_doclist = json.dumps([d.fields for d in doclist])
		CacheItem(self.name).set(json_doclist)

def get(dt, form=1):
	"""
	Load "DocType" - called by form builder, report buider and from code.py (when there is no cache)
	"""
	if not dt: return []

	doclist = _DocType(dt).make_doclist(form)	
	return doclist

# Deprecate after import_docs rewrite
def get_field_property(dt, fieldname, property):
	"""
		get a field property, override it from property setter if specified
	"""
	field = webnotes.conn.sql("""
		select name, `%s` 
		from tabDocField 
		where parent=%s and fieldname=%s""" % (property, '%s', '%s'), (dt, fieldname))
		
	prop = webnotes.conn.sql("""
		select value 
		from `tabProperty Setter` 
		where doc_type=%s and field_name=%s and property=%s""", (dt, fieldname, property))
	if prop: 
		return prop[0][0]
	else:
		return field[0][1]

def get_property(dt, property, fieldname=None):
	"""
		get a doctype property, override it from property setter if specified
	"""
	if fieldname:
		prop = webnotes.conn.sql("""
			select value 
			from `tabProperty Setter` 
			where doc_type=%s and field_name=%s
			and property=%s""", (dt, fieldname, property))
		if prop: 
			return prop[0][0]
		else:
			val = webnotes.conn.sql("""\
				SELECT %s FROM `tabDocField`
				WHERE parent = %s AND fieldname = %s""" % \
				(property, '%s', '%s'), (dt, fieldname))
			if val and val[0][0]: return val[0][0] or ''
	else:
		prop = webnotes.conn.sql("""
			select value 
			from `tabProperty Setter` 
			where doc_type=%s and doctype_or_field='DocType'
			and property=%s""", (dt, property))
		if prop: 
			return prop[0][0]
		else:
			return webnotes.conn.get_value('DocType', dt, property)

# Test Cases
import unittest

class DocTypeTest(unittest.TestCase):
	def setUp(self):
		self.name = 'Sales Order'
		self.dt = _DocType(self.name)

	def tearDown(self):
		webnotes.conn.rollback()

	def test_make_doclist(self):
		doclist = self.dt.make_doclist()
		for d in doclist:
			print d.idx, d.doctype, d.name, d.parent
			if not d.doctype: print d.fields
			#print "--", d.name, "--"
			#print d.doctype
		self.assertTrue(doclist)

	def test_get_custom_fields(self):
		return
		doclist = self.dt.get_custom_fields(self.name)
		for d in doclist:
			print "--", d.name, "--"
			print d.fields
		self.assertTrue(doclist)
