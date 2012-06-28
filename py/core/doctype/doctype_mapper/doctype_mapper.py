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

from webnotes.utils import cint, cstr, default_fields, flt, formatdate, get_defaults, getdate, now, nowdate, replace_newlines, set_default
from webnotes.model import db_exists, default_fields
from webnotes.model.doc import Document, addchild, getchildren, make_autoname
from webnotes.model.doclist import getlist
from webnotes.model.code import get_obj
from webnotes import session, form, msgprint, errprint
from webnotes.model.doctype import get

set = webnotes.conn.set
sql = webnotes.conn.sql
get_value = webnotes.conn.get_value
in_transaction = webnotes.conn.in_transaction
convert_to_lists = webnotes.conn.convert_to_lists
	
# -----------------------------------------------------------------------------------------


class DocType:
	def __init__(self, doc, doclist=[]):
		self.doc = doc
		self.doclist = doclist
		self.ref_doc = ''
		
	#---------------------------------------------------------------------------
	def autoname(self):
		self.doc.name = make_autoname(self.doc.from_doctype + '-' + self.doc.to_doctype)

	
	# Maps the fields in 'To DocType'
	#---------------------------------------------------------------------------
	def dt_map(self, from_doctype, to_doctype, from_docname, to_doc, doclist, from_to_list = '[]'):
		'''
			String <from_doctype> : contains the name of DocType initiating the function
			String <to_doctype>	 : contains the name of DocType created by the function
			String <from_docname> : contains ID(name) of 'from_doctype'
			String <to_doc>			 : contains doc of 'to_doctype'
			String <doclist>			: contains doclist of 'to_doctype'
			String <from_to_list> : contains list of tables which will be mapped
		'''
		
		if not from_docname:
			msgprint(from_doctype + " not selected for mapping", raise_exception=1)
		
		# Validate reference doc docstatus
		self.ref_doc = from_docname
		self.check_ref_docstatus()
		
		if not doclist:
			doclist.append(to_doc)

		tbl_list = sql("""\
			select from_table, to_table, from_field, to_field, match_id, validation_logic
			from `tabTable Mapper Detail` where parent ="%s" order by match_id""" \
			% self.doc.name, as_dict=1)

		for t in tbl_list:
			if [t['from_table'], t['to_table']] in eval(from_to_list):
				self.map_fields(t, from_doctype, from_docname, to_doc, doclist)
		
		# Doclist is required when called from server side for refreshing table
		return doclist


	#---------------------------------------------------------------------------
	def map_fields(self, t, from_dt, from_dn, to_doc, doclist):
		"""
			Creates from, to obj and maps flds as per mapper and with same name
		"""
		flds = self.get_mapper_fields(t)
		flds += self.get_fields_with_same_name(t, flds)

		if flds:
			from_docnames = self.get_docnames(t, from_dt, from_dn)
		
			for dn in from_docnames:		
				# Creates object for 'From DocType', it can be parent or child
				from_doc_obj = Document(t['from_table'], dn[0])
			
				# Add a row in target table in 'To DocType' and returns obj
				if t['to_table'] != self.doc.to_doctype:
					to_doc_obj = addchild(to_doc, t['to_field'], t['to_table'], 1, doclist)
				else:
					to_doc_obj = to_doc

				self.set_value(flds, from_doc_obj, to_doc_obj)
				
	#---------------------------------------------------------------------------	
	def get_docnames(self, t, from_dt, from_dn):
		"""
			Returns docnames of source document (parent/child)
		"""
		docnames = ()
		if t['from_table'] == self.doc.from_doctype:
			docnames = sql("""select name from `tab%s` where name = "%s" and %s""" \
				% (from_dt, from_dn, t['validation_logic']))			
			if not docnames:
				msgprint("Validation failed in doctype mapper. Please contact Administrator.", raise_exception=1)
		else:
			docnames = sql("""\
				select name from `tab%s`
				where parent="%s" and parenttype = "%s" and %s order by idx""" \
				% (t['from_table'], from_dn, self.doc.from_doctype, t['validation_logic']))
		
		return docnames
	
	
	#---------------------------------------------------------------------------
	def get_mapper_fields(self, t):	
		return [[f[0], f[1], f[2]] for f in sql("""
			select from_field, to_field, map 
			from `tabField Mapper Detail` 
			where parent = "%s" and match_id = %s		
		""" % (self.doc.name, t['match_id']))]


	#---------------------------------------------------------------------------
	def get_fields_with_same_name(self, t, flds):
		"""
			Returns field list with same name in from and to doctype
		"""
		import copy
		exception_flds = copy.copy(default_fields)
		exception_flds += [f[1] for f in flds]
		
		from_flds = [d.fieldname for d in get(t['from_table'], 0) \
			if cint(d.no_copy) == 0 and d.docstatus != 2 and d.fieldname \
			and d.fieldtype not in ('Table', 'Section Break', 'Column Break', 'HTML')]

		to_flds = [d.fieldname for d in get(t['to_table'], 0) \
			if cint(d.no_copy) == 0 and d.docstatus != 2 and d.fieldname \
			and d.fieldtype not in ('Table', 'Section Break', 'Column Break', 'HTML')]

		similar_flds = [[d, d, 'Yes'] for d in from_flds \
			if d in to_flds and d not in exception_flds]

		return similar_flds
		
	#---------------------------------------------------------------------------
	def set_value(self, fld_list, obj, to_doc):
		"""
			Assigns value to fields in "To Doctype"
		"""
		for f in fld_list:
			if f[2] == 'Yes':
				if f[0].startswith('eval:'):
					try:
						val = eval(f[0][5:])
					except:
						val = ''
						
					to_doc.fields[f[1]] = val
				else:
					to_doc.fields[f[1]] = obj.fields.get(f[0])
				
				
	#---------------------------------------------------------------------------
	def validate(self):
		"""
			Validate mapper while saving
		"""
		for d in getlist(self.doclist, 'field_mapper_details'):
			# Automatically assigns default value if not entered
			if not d.match_id:
				d.match_id = 0
			if not d.map:
				d.map = 'Yes'
		for d in getlist(self.doclist, 'table_mapper_details'):
			if not d.reference_doctype_key:
				d.reference_doctype_key = ''
			if not d.reference_key:
				d.reference_key = ''
				
		# Check wrong field name
		self.check_fields_in_dt()
		
		
	def check_fields_in_dt(self):
		"""
			Check if any wrong fieldname entered in mapper
		"""
		flds = {}
		for t in getlist(self.doclist, 'table_mapper_details'):
			from_flds = [cstr(d.fieldname) for d in get(t.from_table, 0)]
			to_flds = [cstr(d.fieldname) for d in get(t.to_table, 0)]
			flds[cstr(t.match_id)] = [cstr(t.from_table), from_flds, cstr(t.to_table), to_flds]

		for d in getlist(self.doclist, 'field_mapper_details'):
			# Default fields like name, parent, owner does not exists in DocField
			if d.from_field not in flds[cstr(d.match_id)][1] and d.from_field not in default_fields:
				msgprint("'%s' does not exists in DocType: '%s'" % (cstr(d.from_field), cstr(flds[cstr(d.match_id)][0])))
			if d.to_field not in flds[cstr(d.match_id)][3] and d.to_field not in default_fields:
				msgprint("'%s' does not exists in DocType: '%s'" % (cstr(d.to_field), cstr(flds[cstr(d.match_id)][2])))
					
					
	def validate_reference_value(self, obj, to_docname):
		""" Check consistency of value with reference document"""
		for t in getlist(self.doclist, 'table_mapper_details'):
			# Reference key is the fieldname which will relate to the from_table
			if t.reference_doctype_key:
				for d in getlist(obj.doclist, t.to_field):
					if d.fields[t.reference_doctype_key] == self.doc.from_doctype:
						self.check_consistency(obj.doc, d, to_docname)
						self.check_ref_docstatus()

				
	def get_checklist(self):
		""" Make list of fields whose value will be consistent with prevdoc """
		checklist = []
		for f in getlist(self.doclist, 'field_mapper_details'):
			# Check which field's value will be compared
			if f.checking_operator:
				checklist.append({'from_fld': f.from_field, 'to_fld': f.to_field, 'op': f.checking_operator, 'match_id': f.match_id})
		return checklist
				
	def get_label_and_type(self, from_dt, to_dt):
		"""get label, fieldtype"""
		from_flds, to_flds = {}, {}
		for d in get(from_dt, 0):
			from_flds[d.fieldname] = {'label': d.label, 'fieldtype': d.fieldtype}

		for d in get(to_dt, 0):
			to_flds[d.fieldname] = {'label': d.label, 'fieldtype': d.fieldtype}

		return from_flds, to_flds


	def check_consistency(self, par_obj, child_obj, to_docname):
		"""Check whether values between from_dt and to_dt are consistent"""
		checklist = self.get_checklist()
		self.ref_doc = ''
		for t in getlist(self.doclist, 'table_mapper_details'):
			if t.reference_key and child_obj.fields[t.reference_key]:
				from_flds, to_flds = self.get_label_and_type(t.from_table, t.to_table)
				for cl in checklist:
					if cl['match_id'] == t.match_id:
						if t.to_field:
							cur_val = child_obj.fields[cl['to_fld']]
						else:
							cur_val = par_obj.fields[cl['to_fld']]
						
						if to_flds[cl['to_fld']]['fieldtype'] in ['Currency', 'Float']:
							cur_val = '%.2f' % flt(cur_val)

						if cl['op'] == '=' and to_flds[cl['to_fld']]['fieldtype'] in ['Currency', 'Float']:
							consistent = sql("""select name, %s from `tab%s` \
								where name = %s and %s - %s <= 0.5"""% (cl['from_fld'], t.from_table, '%s', '%s', \
									 cl['from_fld']), (child_obj.fields[t.reference_key], flt(cur_val)))
						else:
							consistent = sql("""select name, %s from `tab%s` \
								where name = %s and %s %s ifnull(%s, '')""" % (cl['from_fld'], t.from_table, \
								'%s', '%s', cl['op'], cl['from_fld']), (child_obj.fields[t.reference_key], \
								to_flds[cl['to_fld']]['fieldtype'] in ('Currency', 'Float', 'Int') \
									and flt(cur_val) or cstr(cur_val)))

						if not self.ref_doc:
							det = sql("""select name, parent from `tab%s` where name = \"%s\"""" % (t.from_table, child_obj.fields[t.reference_key]))
							self.ref_doc = det[0][1] and det[0][1] or det[0][0]

						if not consistent:
							self.give_message(from_flds[cl['from_fld']]['label'], to_flds[cl['to_fld']]['label'], cl['op'])

							
	def give_message(self, from_label, to_label, operator):
		""" Gives message and raise exception"""
		op_in_words = {'=':'equal to ', '>=':'greater than equal to ', '>':'greater than ', '<=':'less than equal to ', '<':'less than '}
		msgprint("%s should be %s %s of %s: %s" % (to_label, op_in_words[operator], from_label, self.doc.from_doctype, self.ref_doc), raise_exception=1)
		

	def check_ref_docstatus(self):
		if self.ref_doc:
			det = sql("""select name, docstatus from `tab%s` where name = \"%s\"""" \
					% (self.doc.from_doctype, self.ref_doc))
			if not det:
				msgprint("%s: %s does not exists in the system" % (self.doc.from_doctype, self.ref_doc), raise_exception=1)
			elif self.doc.ref_doc_submitted and det[0][1] != 1:
				msgprint("%s: %s is not submitted document." % (self.doc.from_doctype, self.ref_doc), raise_exception=1)


	def on_update(self):
		"""
			If developer_mode = 1, mapper will be written to files
		"""
		import conf
		if hasattr(conf, 'developer_mode') and conf.developer_mode:
			from webnotes.modules.export_module import export_to_files
			export_to_files(record_list=[[self.doc.doctype, self.doc.name]])		
