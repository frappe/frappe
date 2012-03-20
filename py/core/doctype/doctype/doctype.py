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

# Please edit this list and import only required elements
import webnotes

from webnotes.utils import now, cint
msgprint = webnotes.msgprint


# -----------------------------------------------------------------------------------------


class DocType:
	def __init__(self, doc=None, doclist=[]):
		self.doc = doc
		self.doclist = doclist

	def change_modified_of_parent(self):
		sql = webnotes.conn.sql
		parent_list = sql('SELECT parent from tabDocField where fieldtype="Table" and options="%s"' % self.doc.name)
		for p in parent_list:
			sql('UPDATE tabDocType SET modified="%s" WHERE `name`="%s"' % (now(), p[0]))

	def scrub_field_names(self):
		restricted = ('name','parent','idx','owner','creation','modified','modified_by','parentfield','parenttype')
		for d in self.doclist:
			if d.parent and d.fieldtype:
				if (not d.fieldname) and (d.fieldtype.lower() in ('data', 'select', 'int', 'float', 'currency', 'table', 'text', 'link', 'date', 'code', 'check', 'read only', 'small_text', 'time')):
					d.fieldname = d.label.strip().lower().replace(' ','_')
					if d.fieldname in restricted:
						d.fieldname = d.fieldname + '1'
	
	def set_version(self):
		self.doc.version = cint(self.doc.version) + 1
	
	#
	# check if this series is not used elsewhere
	#
	def validate_series(self, autoname=None, name=None):
		sql = webnotes.conn.sql
		if not autoname: autoname = self.doc.autoname
		if not name: name = self.doc.name
		
		if autoname and (not autoname.startswith('field:')) and (not autoname.startswith('eval:')) and (not autoname=='Prompt'):
			prefix = autoname.split('.')[0]
			used_in = sql('select name from tabDocType where substring_index(autoname, ".", 1) = %s and name!=%s', (prefix, name))
			if used_in:
				msgprint('<b>Series already in use:</b> The series "%s" is already used in "%s"' % (prefix, used_in[0][0]), raise_exception=1)

	#
	# field validations
	#
	def validate_fields(self):
		"validates fields for incorrect properties and double entries"
		fieldnames = {}
		for d in self.doclist:
			if d.parent and d.fieldtype and d.parent == self.doc.name:
				# check if not double
				if d.fieldname:
					if fieldnames.get(d.fieldname):
						webnotes.msgprint('Fieldname <b>%s</b> appears twice (rows %s and %s). Please rectify' \
						 	% (d.fieldname, str(d.idx + 1), str(fieldnames[d.fieldname] + 1)), raise_exception=1)
					fieldnames[d.fieldname] = d.idx
					
				# check illegal mandatory
				if d.fieldtype in ('HTML', 'Button', 'Section Break', 'Column Break') and d.reqd:
					webnotes.msgprint('%(lable)s [%(fieldtype)s] cannot be mandatory', raise_exception=1)
		
		
	def validate(self):
		self.validate_series()
		self.scrub_field_names()
		self.validate_fields()
		self.set_version()
		self.make_file_list()


	def on_update(self):
		sql = webnotes.conn.sql
		# make schma changes
		from webnotes.model.db_schema import updatedb
		updatedb(self.doc.name)

		self.change_modified_of_parent()
		
		from webnotes import defs
		from webnotes.utils.transfer import in_transfer

		if (not in_transfer) and getattr(webnotes.defs,'developer_mode', 0):
			self.export_doc()

		from webnotes.utils.cache import CacheItem
		CacheItem(self.doc.name).clear()

		
	def export_doc(self):
		from webnotes.modules.export_module import export_to_files
		export_to_files(record_list=[['DocType', self.doc.name]])
		
	def import_doc(self):
		from webnotes.modules.import_module import import_from_files
		import_from_files(record_list=[[self.doc.module, 'doctype', self.doc.name]])		
	
	def make_file_list(self):
		"""
			if allow_attach is checked and the column file_list doesn't exist,
			create a new field 'file_list'
		"""
		if self.doc.allow_attach:
			import webnotes.model.doctype
			temp_doclist = webnotes.model.doctype.get(self.doc.name, form=0)
			if 'file_list' not in [d.fieldname for d in temp_doclist if \
					d.doctype=='DocField']:
				new = self.doc.addchild('fields', 'DocField', 1, self.doclist)
				new.label = 'File List'
				new.fieldtype = 'Text'
				new.fieldname = 'file_list'
				new.hidden = 1
				new.permlevel = 0
				new.print_hide = 1
				new.no_copy = 1
				max_idx = max([d.idx for d in temp_doclist if d.idx])
				max_idx = max_idx and max_idx or 0
				new.idx = max_idx + 1
				new.save()
