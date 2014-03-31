# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals

import frappe
from frappe import msgprint, _
import os

from frappe.utils import now, cint
from frappe.model import no_value_fields
from frappe.model.document import Document

class DocType(Document):
	def validate(self):
		if not frappe.conf.get("developer_mode"):
			frappe.throw("Not in Developer Mode! Set in site_config.json")
		for c in [".", "/", "#", "&", "=", ":", "'", '"']:
			if c in self.name:
				frappe.msgprint(c + " not allowed in name", raise_exception=1)
		self.validate_series()
		self.scrub_field_names()
		self.validate_title_field()
		validate_fields(self.get("fields"))
		validate_permissions(self.get("permissions"))
		self.make_amendable()
		self.check_link_replacement_error()

	def change_modified_of_parent(self):
		if frappe.flags.in_import:
			return
		parent_list = frappe.db.sql("""SELECT parent 
			from tabDocField where fieldtype="Table" and options=%s""", self.name)
		for p in parent_list:
			frappe.db.sql('UPDATE tabDocType SET modified=%s WHERE `name`=%s', (now(), p[0]))

	def scrub_field_names(self):
		restricted = ('name','parent','idx','owner','creation','modified','modified_by',
			'parentfield','parenttype',"file_list")
		for d in self.get("fields"):
			if d.parent and d.fieldtype:
				if (not d.fieldname):
					if d.label:
						d.fieldname = d.label.strip().lower().replace(' ','_')
						if d.fieldname in restricted:
							d.fieldname = d.fieldname + '1'
					else:
						d.fieldname = d.fieldtype.lower().replace(" ","_") + "_" + str(d.idx)
						
	
	def validate_title_field(self):
		if self.title_field and \
			self.title_field not in [d.fieldname for d in self.get("fields")]:
			frappe.throw(_("Title field must be a valid fieldname"))
			
	def validate_series(self, autoname=None, name=None):
		if not autoname: autoname = self.autoname
		if not name: name = self.name
		
		if not autoname and self.get("fields", {"fieldname":"naming_series"}):
			self.autoname = "naming_series:"
		
		if autoname and (not autoname.startswith('field:')) and (not autoname.startswith('eval:')) \
			and (not autoname=='Prompt') and (not autoname.startswith('naming_series:')):
			prefix = autoname.split('.')[0]
			used_in = frappe.db.sql('select name from tabDocType where substring_index(autoname, ".", 1) = %s and name!=%s', (prefix, name))
			if used_in:
				msgprint('<b>Series already in use:</b> The series "%s" is already used in "%s"' % (prefix, used_in[0][0]), raise_exception=1)

	def on_update(self):
		from frappe.model.db_schema import updatedb
		updatedb(self.name)

		self.change_modified_of_parent()
		make_module_and_roles(self)
		
		from frappe import conf
		if (not frappe.flags.in_import) and conf.get('developer_mode') or 0:
			self.export_doc()
			self.make_controller_template()
		
		# update index
		if not self.custom:
			from frappe.modules import load_doctype_module
			module = load_doctype_module(self.name, self.module)
			if hasattr(module, "on_doctype_update"):
				module.on_doctype_update()
		frappe.clear_cache(doctype=self.name)

	def check_link_replacement_error(self):
		for d in self.get("fields", {"fieldtype":"Select"}):
			if (frappe.db.get_value("DocField", d.name, "options") or "").startswith("link:") \
				and not d.options.startswith("link:"):
				frappe.msgprint("link: type Select fields are getting replaced. Please check for %s" % d.label,
					raise_exception=True)

	def on_trash(self):
		frappe.db.sql("delete from `tabCustom Field` where dt = %s", self.name)
		frappe.db.sql("delete from `tabCustom Script` where dt = %s", self.name)
		frappe.db.sql("delete from `tabProperty Setter` where doc_type = %s", self.name)
		frappe.db.sql("delete from `tabReport` where ref_doctype=%s", self.name)
	
	def before_rename(self, old, new, merge=False):
		if merge:
			frappe.throw(_("DocType can not be merged"))
			
	def after_rename(self, old, new, merge=False):
		if self.issingle:
			frappe.db.sql("""update tabSingles set doctype=%s where doctype=%s""", (new, old))
		else:
			frappe.db.sql("rename table `tab%s` to `tab%s`" % (old, new))
	
	def export_doc(self):
		from frappe.modules.export_file import export_to_files
		export_to_files(record_list=[['DocType', self.name]])
		
	def import_doc(self):
		from frappe.modules.import_module import import_from_files
		import_from_files(record_list=[[self.module, 'doctype', self.name]])		

	def make_controller_template(self):
		from frappe.modules import get_doc_path, get_module_path, scrub
		
		pypath = os.path.join(get_doc_path(self.module, 
			self.doctype, self.name), scrub(self.name) + '.py')

		if not os.path.exists(pypath):
			# get app publisher for copyright
			app = frappe.local.module_app[frappe.scrub(self.module)]
			if not app:
				frappe.throw("App not found!")
			app_publisher = frappe.get_hooks(hook="app_publisher", app_name=app)[0]
			
			with open(pypath, 'w') as pyfile:
				with open(os.path.join(get_module_path("core"), "doctype", "doctype", 
					"doctype_template.py"), 'r') as srcfile:
					pyfile.write(srcfile.read().format(app_publisher=app_publisher, classname=self.name.replace(" ", "")))
	
	def make_amendable(self):
		"""
			if is_submittable is set, add amended_from docfields
		"""
		if self.is_submittable:
			if not frappe.db.sql("""select name from tabDocField 
				where fieldname = 'amended_from' and parent = %s""", self.name):
					self.append("fields", {
						"label": "Amended From",
						"fieldtype": "Link",
						"fieldname": "amended_from",
						"options": self.name,
						"read_only": 1,
						"print_hide": 1,
						"no_copy": 1
					})
				
	def get_max_idx(self):
		max_idx = frappe.db.sql("""select max(idx) from `tabDocField` where parent = %s""", 
			self.name)
		return max_idx and max_idx[0][0] or 0

def validate_fields_for_doctype(doctype):
	validate_fields(frappe.get_meta(doctype).get("fields"))
		
def validate_fields(fields):
	def check_illegal_characters(fieldname):
		for c in ['.', ',', ' ', '-', '&', '%', '=', '"', "'", '*', '$', 
			'(', ')', '[', ']', '/']:
			if c in fieldname:
				frappe.msgprint("'%s' not allowed in fieldname (%s)" % (c, fieldname))
	
	def check_unique_fieldname(fieldname):
		duplicates = filter(None, map(lambda df: df.fieldname==fieldname and str(df.idx) or None, fields))
		if len(duplicates) > 1:
			frappe.msgprint('Fieldname <b>%s</b> appears more than once in rows (%s). Please rectify' \
			 	% (fieldname, ', '.join(duplicates)), raise_exception=1)
	
	def check_illegal_mandatory(d):
		if d.fieldtype in ('HTML', 'Button', 'Section Break', 'Column Break') and d.reqd:
			frappe.msgprint('%(label)s [%(fieldtype)s] cannot be mandatory' % d.fields, 
				raise_exception=1)
	
	def check_link_table_options(d):
		if d.fieldtype in ("Link", "Table"):
			if not d.options:
				frappe.msgprint("""#%(idx)s %(label)s: Options must be specified for Link and Table type fields""" % d.fields, 
					raise_exception=1)
			if d.options=="[Select]":
				return
			if d.options != d.parent and not frappe.db.exists("DocType", d.options):
				frappe.msgprint("""#%(idx)s %(label)s: Options %(options)s must be a valid "DocType" for Link and Table type fields""" % d.fields, 
					raise_exception=1)

	def check_hidden_and_mandatory(d):
		if d.hidden and d.reqd and not d.default:
			frappe.msgprint("""#%(idx)s %(label)s: Cannot be hidden and mandatory (reqd) without default""" % d.fields,
				raise_exception=True)

	def check_min_items_in_list(fields):
		if len(filter(lambda d: d.in_list_view, fields))==0:
			for d in fields[:5]:
				d.in_list_view = 1
				
	def check_width(d):
		if d.fieldtype == "Currency" and cint(d.width) < 100:
			frappe.msgprint("Minimum width for FieldType 'Currency' is 100px", raise_exception=1)

	def check_in_list_view(d):
		if d.in_list_view and d.fieldtype!="Image" and (d.fieldtype in no_value_fields):
			frappe.msgprint("'In List View' not allowed for field of type '%s'" % d.fieldtype, raise_exception=1)

	for d in fields:
		if not d.permlevel: d.permlevel = 0
		if not d.fieldname:
			frappe.msgprint("Fieldname is mandatory in row %s" % d.idx, raise_exception=1)
		check_illegal_characters(d.fieldname)
		check_unique_fieldname(d.fieldname)
		check_illegal_mandatory(d)
		check_link_table_options(d)
		check_hidden_and_mandatory(d)
		check_in_list_view(d)

	check_min_items_in_list(fields)

def validate_permissions_for_doctype(doctype, for_remove=False):
	validate_permissions(frappe.get_meta(doctype, cached=False).get("permissions"), for_remove)
	
def validate_permissions(permissions, for_remove=False):
	doctype = permissions and permissions[0].parent
	issingle = issubmittable = isimportable = False
	if doctype and not doctype.startswith("New DocType"):
		values = frappe.db.get_value("DocType", doctype, 
			["issingle", "is_submittable", "allow_import"], as_dict=True)
		issingle = cint(values.issingle)
		issubmittable = cint(values.is_submittable)
		isimportable = cint(values.allow_import)

	def get_txt(d):
		return "For %s (level %s) in %s, row #%s:" % (d.role, d.permlevel, d.parent, d.idx)
		
	def check_atleast_one_set(d):
		if not d.read and not d.write and not d.submit and not d.cancel and not d.create:
			frappe.msgprint(get_txt(d) + " Atleast one of Read, Write, Create, Submit, Cancel must be set.",
			 	raise_exception=True)
		
	def check_double(d):
		similar = permissions.get({
			"role":d.role,
			"permlevel":d.permlevel,
			"match": d.match
		})
		
		if len(similar) > 1:
			frappe.msgprint(get_txt(d) + " Only one rule allowed for a particular Role and Level.", 
				raise_exception=True)
	
	def check_level_zero_is_set(d):
		if cint(d.permlevel) > 0 and d.role != 'All':
			if not permissions.get({"role": d.role, "permlevel": 0}):
				frappe.msgprint(get_txt(d) + " Higher level permissions are meaningless if level 0 permission is not set.",
					raise_exception=True)
					
			if d.create or d.submit or d.cancel or d.amend or d.match: 
				frappe.msgprint("Create, Submit, Cancel, Amend, Match has no meaning at level " + d.permlevel,
					raise_exception=True)
	
	def check_permission_dependency(d):
		if d.cancel and not d.submit:
			frappe.msgprint(get_txt(d) + " Cannot set Cancel permission if Submit is not set.",
				raise_exception=True)
		if (d.submit or d.cancel or d.amend) and not d.write:
			frappe.msgprint(get_txt(d) + " Cannot set Submit, Cancel, Amend permission if Write is not set.",
				raise_exception=True)
		if d.amend and not d.write:
			frappe.msgprint(get_txt(d) + " Cannot set Amend if Cancel is not set.",
				raise_exception=True)
		if (d.get("import") or d.export) and not d.report:
			frappe.msgprint(get_txt(d) + " Cannot set Import or Export permission if Report is not set.",
				raise_exception=True)
		if d.get("import") and not d.create:
			frappe.msgprint(get_txt(d) + " Cannot set Import if Create is not set.",
				raise_exception=True)
	
	def remove_rights_for_single(d):
		if not issingle:
			return
		
		if d.report:
			frappe.msgprint("{doctype} {meaningless}".format(doctype=doctype,
				meaningless=_("is a single DocType, permission of type Report is meaningless.")))
			d.report = 0
			d.set("import", 0)
			d.set("export", 0)
			
		if d.restrict:
			frappe.msgprint("{doctype} {meaningless}".format(doctype=doctype,
				meaningless=_("is a single DocType, permission of type Restrict is meaningless.")))
			d.restrict = 0
	
	def check_if_submittable(d):
		if d.submit and not issubmittable:
			frappe.msgprint(doctype + " is not Submittable, cannot assign submit rights.",
				raise_exception=True)
		elif d.amend and not issubmittable:
			frappe.msgprint(doctype + " is not Submittable, cannot assign amend rights.",
				raise_exception=True)
	
	def check_if_importable(d):
		if d.get("import") and not isimportable:
			frappe.throw("{doctype}: {not_importable}".format(doctype=doctype,
				not_importable=_("is not allowed to be imported, cannot assign import rights.")))
	
	for d in permissions:
		if not d.permlevel: 
			d.permlevel=0
		check_atleast_one_set(d)
		if not for_remove:
			check_double(d)
			check_permission_dependency(d)
			check_if_submittable(d)
			check_if_importable(d)
		check_level_zero_is_set(d)
		remove_rights_for_single(d)

def make_module_and_roles(doc, perm_fieldname="permissions"):
	try:
		if not frappe.db.exists("Module Def", doc.module):
			m = frappe.get_doc({"doctype": "Module Def", "module_name": doc.module})
			m.ignore_mandatory = m.ignore_permissions = True
			m.insert()
		
		default_roles = ["Administrator", "Guest", "All"]
		roles = [p.role for p in doc.get("permissions") or []] + default_roles
		
		for role in list(set(roles)):
			if not frappe.db.exists("Role", role):
				r = frappe.get_doc({"doctype": "Role", "role_name": role})
				r.role_name = role
				r.ignore_mandatory = r.ignore_permissions = True
				r.insert()
	except frappe.DoesNotExistError, e:
		pass
	except frappe.SQLError, e:
		if e.args[0]==1146:
			pass
		else:
			raise
