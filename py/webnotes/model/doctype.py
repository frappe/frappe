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
# DocLayer:
#	Allow type changing

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
		if form:
			cached_doclist = self.load_from_cache()
			if cached_doclist: return cached_doclist

		# Get parent doc and its fields
		doclist = webnotes.model.doc.get('DocType', self.name, 1)
		doclist += self.get_custom_fields(self.name)

		if form:
			table_fields = self.get_table_fields(doclist)
			for t in table_fields:
				# Get child doc and its fields
				table_doclist = webnotes.model.doc.get('DocType', t[0], 1)
				table_doclist += self.get_custom_fields(t[0])
				doclist += table_doclist

		self.apply_property_setters(doclist)
		
		if form:
			self.load_select_options(doclist)
			self.load_custom_scripts(doclist)
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
		property_dict = {}
		doc_type_list = list(set(
			d.doctype=='DocType' and d.name or d.parent
			for d in doclist))
		in_string = '", "'.join(doc_type_list)
		for ps in webnotes.conn.sql("""\
			SELECT doc_name, property, property_type, value
			FROM `tabProperty Setter`
			WHERE doc_type IN ("%s")""" % in_string, as_dict=1):
			property_dict.setdefault(ps.get('doc_name'), []).append(ps)
		return property_dict, doc_type_list

	def update_field_properties(self, d, property_dict):
		"""
			apply properties except previous_field ones
		"""
		if not property_dict.get(d.name): return
		
		from webnotes.utils import cint
		prop_updates = dict([
			prop.get('property_type')=='Check'
			and [prop.get('property'), cint(prop.get('value'))]
			or [prop.get('property'), prop.get('value')]
			for prop in property_dict.get(d.name)
			if prop.get('property')!='previous_field'
		])
		
		prop_updates and d.fields.update(prop_updates)

	def apply_previous_field_properties(self, doclist, property_dict,
			doc_type_list):
		"""

		"""
		prev_field_dict = self.get_previous_field_properties(property_dict)
		if not prev_field_dict: return

		for doc_type in doc_type_list:
			docfields = self.get_sorted_docfields(doclist, doc_type)
			docfields = self.sort_docfields(docfields, prev_field_dict)
			if docfields: self.change_idx(doclist, docfields)

	def get_previous_field_properties(self, property_dict):
		"""
			setup prev_field_dict
		"""
		from webnotes.utils import cstr
		prev_field_list = []
		for prop_list in property_dict.values():
			for prop in prop_list:
				if prop.get('property')=='previous_field':
					prev_field_list.append([cstr(prop.get('value')),
						cstr(prop.get('doc_name'))])
					break
		if not prev_field_list: return
		return dict(prev_field_list)

	def get_sorted_docfields(self, doclist, doc_type):
		"""
			get a sorted list of docfield names
		"""
		sorted_list = sorted([
				d for d in doclist
				if d.doctype == 'DocField'
				and d.parent == doc_type
			], key=lambda df: df.idx)
		return [d.name for d in sorted_list]

	def sort_docfields(self, docfields, prev_field_dict):
		"""
			
		"""
		temp_dict = dict([name, prev_field_dict.get(name)]
				for name in docfields if name in prev_field_dict)
		if not temp_dict: return
		prev_field = 'None' in temp_dict and 'None' or docfields[0]
		i = 0
		while temp_dict:
			get_next_docfield = True
			cur_field = temp_dict.get(prev_field)
			if cur_field and cur_field in docfields:
				try:
					del temp_dict[prev_field]
					docfields.remove(cur_field)
					if prev_field in docfields:
						docfields.insert(docfields.index(prev_field) + 1,
								cur_field)
					elif prev_field == 'None':
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

	def change_idx(self, doclist, docfields):
		for d in doclist:
			if d.name in docfields:
				d.idx = docfields.index(d.name) + 1

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

	def load_custom_scripts(self, doclist):
		"""
			Loads custom js and css
		"""
		from webnotes.modules import Module
		from webnotes.model.code import get_custom_script

		doc = doclist[0]
		custom = get_custom_script(doc.name, 'Client') or ''
		module = Module(doc.module)
		doc.fields.update({
			'__js': module.get_doc_file(
				'doctype', doc.name, '.js').read() + '\n' + custom,
			'__css': module.get_doc_file(
				'doctype', doc.name, '.css').read(),
		})

		# clear code
		if self.name != 'DocType':
			doc.server_code = doc.server_code_core = doc.client_script \
			= doc.client_script_core = doc.server_code_compiled = None

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
		CacheItem(self.name).set(json_doclist, 3600)

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
		where doc_type=%s and doc_name=%s and property=%s""", (dt, field[0][0], property))
	if prop: 
		return prop[0][0]
	else:
		return field[0][1]

# Deprecate after docbrowser rewrite,
# used in tags
def get_property(dt, property):
	"""
		get a doctype property, override it from property setter if specified
	"""
	prop = webnotes.conn.sql("""
		select value 
		from `tabProperty Setter` 
		where doc_type=%s and doc_name=%s and property=%s""", (dt, dt, property))
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
			print d.doctype, d.name, d.parent
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
