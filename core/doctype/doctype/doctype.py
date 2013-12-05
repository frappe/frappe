# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals

import webnotes
from webnotes import msgprint, _
import os

from webnotes.utils import now, cint
from webnotes.model import no_value_fields

class DocType:
	def __init__(self, doc=None, doclist=[]):
		self.doc = doc
		self.doclist = doclist

	def validate(self):
		for c in [".", "/", "#", "&", "=", ":", "'", '"']:
			if c in self.doc.name:
				webnotes.msgprint(c + " not allowed in name", raise_exception=1)
		self.validate_series()
		self.scrub_field_names()
		validate_fields(self.doclist.get({"doctype":"DocField"}))
		validate_permissions(self.doclist.get({"doctype":"DocPerm"}))
		self.set_version()
		self.make_amendable()
		self.check_link_replacement_error()

	def change_modified_of_parent(self):
		if webnotes.flags.in_import:
			return
		parent_list = webnotes.conn.sql("""SELECT parent 
			from tabDocField where fieldtype="Table" and options="%s" """ % self.doc.name)
		for p in parent_list:
			webnotes.conn.sql('''UPDATE tabDocType SET modified="%s" 
				WHERE `name`="%s"''' % (now(), p[0]))

	def scrub_field_names(self):
		restricted = ('name','parent','idx','owner','creation','modified','modified_by',
			'parentfield','parenttype',"file_list")
		for d in self.doclist:
			if d.parent and d.fieldtype:
				if (not d.fieldname):
					if d.label:
						d.fieldname = d.label.strip().lower().replace(' ','_')
						if d.fieldname in restricted:
							d.fieldname = d.fieldname + '1'
					else:
						d.fieldname = d.fieldtype.lower().replace(" ","_") + "_" + str(d.idx)
						
	
	def set_version(self):
		self.doc.version = cint(self.doc.version) + 1
	
	def validate_series(self, autoname=None, name=None):
		if not autoname: autoname = self.doc.autoname
		if not name: name = self.doc.name
		
		if not autoname and self.doclist.get({"fieldname":"naming_series"}):
			self.doc.autoname = "naming_series:"
		
		if autoname and (not autoname.startswith('field:')) and (not autoname.startswith('eval:')) \
			and (not autoname=='Prompt') and (not autoname.startswith('naming_series:')):
			prefix = autoname.split('.')[0]
			used_in = webnotes.conn.sql('select name from tabDocType where substring_index(autoname, ".", 1) = %s and name!=%s', (prefix, name))
			if used_in:
				msgprint('<b>Series already in use:</b> The series "%s" is already used in "%s"' % (prefix, used_in[0][0]), raise_exception=1)

	def on_update(self):
		from webnotes.model.db_schema import updatedb
		updatedb(self.doc.name)

		self.change_modified_of_parent()
		make_module_and_roles(self.doclist)
		
		from webnotes import conf
		if (not webnotes.flags.in_import) and conf.get('developer_mode') or 0:
			self.export_doc()
			self.make_controller_template()
		
		# update index
		if not self.doc.custom:
			from webnotes.model.code import load_doctype_module
			module = load_doctype_module( self.doc.name, self.doc.module)
			if hasattr(module, "on_doctype_update"):
				module.on_doctype_update()
		webnotes.clear_cache(doctype=self.doc.name)

	def check_link_replacement_error(self):
		for d in self.doclist.get({"doctype":"DocField", "fieldtype":"Select"}):
			if (webnotes.conn.get_value("DocField", d.name, "options") or "").startswith("link:") \
				and not d.options.startswith("link:"):
				webnotes.msgprint("link: type Select fields are getting replaced. Please check for %s" % d.label,
					raise_exception=True)

	def on_trash(self):
		webnotes.conn.sql("delete from `tabCustom Field` where dt = %s", self.doc.name)
		webnotes.conn.sql("delete from `tabCustom Script` where dt = %s", self.doc.name)
		webnotes.conn.sql("delete from `tabProperty Setter` where doc_type = %s", self.doc.name)
		webnotes.conn.sql("delete from `tabReport` where ref_doctype=%s", self.doc.name)
	
	def before_rename(self, old, new, merge=False):
		if merge:
			webnotes.throw(_("DocType can not be merged"))
			
	def after_rename(self, old, new, merge=False):
		if self.doc.issingle:
			webnotes.conn.sql("""update tabSingles set doctype=%s where doctype=%s""", (new, old))
		else:
			webnotes.conn.sql("rename table `tab%s` to `tab%s`" % (old, new))
	
	def export_doc(self):
		from webnotes.modules.export_file import export_to_files
		export_to_files(record_list=[['DocType', self.doc.name]])
		
	def import_doc(self):
		from webnotes.modules.import_module import import_from_files
		import_from_files(record_list=[[self.doc.module, 'doctype', self.doc.name]])		

	def make_controller_template(self):
		from webnotes.modules import get_doc_path, get_module_path, scrub
		
		pypath = os.path.join(get_doc_path(self.doc.module, 
			self.doc.doctype, self.doc.name), scrub(self.doc.name) + '.py')

		if not os.path.exists(pypath):
			with open(pypath, 'w') as pyfile:
				with open(os.path.join(get_module_path("core"), "doctype", "doctype", 
					"doctype_template.py"), 'r') as srcfile:
					pyfile.write(srcfile.read())
	
	def make_amendable(self):
		"""
			if is_submittable is set, add amended_from docfields
		"""
		if self.doc.is_submittable:
			if not webnotes.conn.sql("""select name from tabDocField 
				where fieldname = 'amended_from' and parent = %s""", self.doc.name):
					new = self.doc.addchild('fields', 'DocField', self.doclist)
					new.label = 'Amended From'
					new.fieldtype = 'Link'
					new.fieldname = 'amended_from'
					new.options = self.doc.name
					new.permlevel = 0
					new.read_only = 1
					new.print_hide = 1
					new.no_copy = 1
					new.idx = self.get_max_idx() + 1
				
	def get_max_idx(self):
		max_idx = webnotes.conn.sql("""select max(idx) from `tabDocField` where parent = %s""", 
			self.doc.name)
		return max_idx and max_idx[0][0] or 0

def validate_fields_for_doctype(doctype):
	from webnotes.model.doctype import get
	validate_fields(get(doctype, cached=False).get({"parent":doctype, 
		"doctype":"DocField"}))
		
def validate_fields(fields):
	def check_illegal_characters(fieldname):
		for c in ['.', ',', ' ', '-', '&', '%', '=', '"', "'", '*', '$', 
			'(', ')', '[', ']', '/']:
			if c in fieldname:
				webnotes.msgprint("'%s' not allowed in fieldname (%s)" % (c, fieldname))
	
	def check_unique_fieldname(fieldname):
		duplicates = filter(None, map(lambda df: df.fieldname==fieldname and str(df.idx) or None, fields))
		if len(duplicates) > 1:
			webnotes.msgprint('Fieldname <b>%s</b> appears more than once in rows (%s). Please rectify' \
			 	% (fieldname, ', '.join(duplicates)), raise_exception=1)
	
	def check_illegal_mandatory(d):
		if d.fieldtype in ('HTML', 'Button', 'Section Break', 'Column Break') and d.reqd:
			webnotes.msgprint('%(label)s [%(fieldtype)s] cannot be mandatory' % d.fields, 
				raise_exception=1)
	
	def check_link_table_options(d):
		if d.fieldtype in ("Link", "Table"):
			if not d.options:
				webnotes.msgprint("""#%(idx)s %(label)s: Options must be specified for Link and Table type fields""" % d.fields, 
					raise_exception=1)
			if d.options=="[Select]":
				return
			if not webnotes.conn.exists("DocType", d.options):
				webnotes.msgprint("""#%(idx)s %(label)s: Options %(options)s must be a valid "DocType" for Link and Table type fields""" % d.fields, 
					raise_exception=1)

	def check_hidden_and_mandatory(d):
		if d.hidden and d.reqd and not d.default:
			webnotes.msgprint("""#%(idx)s %(label)s: Cannot be hidden and mandatory (reqd) without default""" % d.fields,
				raise_exception=True)

	def check_max_items_in_list(fields):
		count = 0
		for d in fields:
			if d.in_list_view: count+=1
		if count > 5:
			webnotes.msgprint("""Max 5 Fields can be set as 'In List View', please unselect a field before selecting a new one.""")
				
	def check_width(d):
		if d.fieldtype == "Currency" and cint(d.width) < 100:
			webnotes.msgprint("Minimum width for FieldType 'Currency' is 100px", raise_exception=1)

	def check_in_list_view(d):
		if d.in_list_view and d.fieldtype!="Image" and (d.fieldtype in no_value_fields):
			webnotes.msgprint("'In List View' not allowed for field of type '%s'" % d.fieldtype, raise_exception=1)

	for d in fields:
		if not d.permlevel: d.permlevel = 0
		if not d.fieldname:
			webnotes.msgprint("Fieldname is mandatory in row %s" % d.idx, raise_exception=1)
		check_illegal_characters(d.fieldname)
		check_unique_fieldname(d.fieldname)
		check_illegal_mandatory(d)
		check_link_table_options(d)
		check_hidden_and_mandatory(d)
		check_in_list_view(d)

def validate_permissions_for_doctype(doctype, for_remove=False):
	from webnotes.model.doctype import get
	validate_permissions(get(doctype, cached=False).get({"parent":doctype, 
		"doctype":"DocPerm"}), for_remove)

def validate_permissions(permissions, for_remove=False):
	doctype = permissions and permissions[0].parent
	issingle = issubmittable = False
	if doctype:
		issingle = cint(webnotes.conn.get_value("DocType", doctype, "issingle"))
		issubmittable = cint(webnotes.conn.get_value("DocType", doctype, "is_submittable"))
			
	def get_txt(d):
		return "For %s (level %s) in %s row %s:" % (d.role, d.permlevel, d.parent, d.idx)
		
	def check_atleast_one_set(d):
		if not d.read and not d.write and not d.submit and not d.cancel and not d.create:
			webnotes.msgprint(get_txt(d) + " Atleast one of Read, Write, Create, Submit, Cancel must be set.",
			 	raise_exception=True)
		
	def check_double(d):
		similar = permissions.get({
			"role":d.role,
			"permlevel":d.permlevel,
			"match": d.match
		})
		
		if len(similar) > 1:
			webnotes.msgprint(get_txt(d) + " Only one rule allowed for a particular Role and Level.", 
				raise_exception=True)
	
	def check_level_zero_is_set(d):
		if cint(d.permlevel) > 0 and d.role != 'All':
			if not permissions.get({"role": d.role, "permlevel": 0}):
				webnotes.msgprint(get_txt(d) + " Higher level permissions are meaningless if level 0 permission is not set.",
					raise_exception=True)
					
			if d.create or d.submit or d.cancel or d.amend or d.match: 
				webnotes.msgprint("Create, Submit, Cancel, Amend, Match has no meaning at level " + d.permlevel,
					raise_exception=True)
	
	def check_permission_dependency(d):
		if d.write and not d.read:
			webnotes.msgprint(get_txt(d) + " Cannot set Write permission if Read is not set.",
				raise_exception=True)
		if (d.submit or d.cancel or d.amend) and not d.write:
			webnotes.msgprint(get_txt(d) + " Cannot set Submit, Cancel, Amend permission if Write is not set.",
				raise_exception=True)
		if d.amend and not d.write:
			webnotes.msgprint(get_txt(d) + " Cannot set Amend if Cancel is not set.",
				raise_exception=True)
	
	def remove_report_if_single(d):
		if d.report and issingle:
			webnotes.msgprint(doctype + " is a single DocType, permission of type Report is meaningless.")
	
	def check_if_submittable(d):
		if d.submit and not issubmittable:
			webnotes.msgprint(doctype + " is not Submittable, cannot assign submit rights.",
				raise_exception=True)
		elif d.amend and not issubmittable:
			webnotes.msgprint(doctype + " is not Submittable, cannot assign amend rights.",
				raise_exception=True)
	
	for d in permissions:
		if not d.permlevel: 
			d.permlevel=0
		check_atleast_one_set(d)
		if not for_remove:
			check_double(d)
			check_permission_dependency(d)
			check_if_submittable(d)
		check_level_zero_is_set(d)
		remove_report_if_single(d)

def make_module_and_roles(doclist, perm_doctype="DocPerm"):
	try:
		if not webnotes.conn.exists("Module Def", doclist[0].module):
			m = webnotes.bean({"doctype": "Module Def", "module_name": doclist[0].module})
			m.insert()
		
		roles = list(set(p.role for p in doclist.get({"doctype": perm_doctype})))
		for role in roles:
			if not webnotes.conn.exists("Role", role):
				r = webnotes.bean({"doctype": "Role", "role_name": role})
				r.doc.role_name = role
				r.insert()
	except webnotes.DoesNotExistError, e:
		pass
	except webnotes.SQLError, e:
		if e.args[0]==1146:
			pass
		else:
			raise
