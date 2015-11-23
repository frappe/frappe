# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import re
import frappe
from frappe import _

from frappe.utils import now, cint
from frappe.model import no_value_fields
from frappe.model.document import Document
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.desk.notifications import delete_notification_count_for
from frappe.modules import make_boilerplate
from frappe.model.db_schema import validate_column_name

class InvalidFieldNameError(frappe.ValidationError): pass

form_grid_templates = {
	"fields": "templates/form_grid/fields.html"
}

class DocType(Document):
	def get_feed(self):
		return self.name

	def validate(self):
		"""Validate DocType before saving.

		- Check if developer mode is set.
		- Validate series
		- Check fieldnames (duplication etc)
		- Clear permission table for child tables
		- Add `amended_from` and `ameneded_by` if Amendable"""
		self.check_developer_mode()
		for c in [".", "/", "#", "&", "=", ":", "'", '"']:
			if c in self.name:
				frappe.throw(_("{0} not allowed in name").format(c))
		self.validate_series()
		self.scrub_field_names()
		self.validate_document_type()
		validate_fields(self)

		if self.istable:
			# no permission records for child table
			self.permissions = []
		else:
			validate_permissions(self)

		self.make_amendable()

	def check_developer_mode(self):
		"""Throw exception if not developer mode or via patch"""
		if frappe.flags.in_patch:
			return

		if not frappe.conf.get("developer_mode") and not self.custom:
			frappe.throw(_("Not in Developer Mode! Set in site_config.json or make 'Custom' DocType."))

	def validate_document_type(self):
		if self.document_type=="Transaction":
			self.document_type = "Document"
		if self.document_type=="Master":
			self.document_type = "Setup"

	def change_modified_of_parent(self):
		"""Change the timestamp of parent DocType if the current one is a child to clear caches."""
		if frappe.flags.in_import:
			return
		parent_list = frappe.db.sql("""SELECT parent
			from tabDocField where fieldtype="Table" and options=%s""", self.name)
		for p in parent_list:
			frappe.db.sql('UPDATE tabDocType SET modified=%s WHERE `name`=%s', (now(), p[0]))

	def scrub_field_names(self):
		"""Sluggify fieldnames if not set from Label."""
		restricted = ('name','parent','creation','modified','modified_by',
			'parentfield','parenttype',"file_list")
		for d in self.get("fields"):
			if d.fieldtype:
				if (not getattr(d, "fieldname", None)):
					if d.label:
						d.fieldname = d.label.strip().lower().replace(' ','_')
						if d.fieldname in restricted:
							d.fieldname = d.fieldname + '1'
					else:
						d.fieldname = d.fieldtype.lower().replace(" ","_") + "_" + str(d.idx)

	def validate_series(self, autoname=None, name=None):
		"""Validate if `autoname` property is correctly set."""
		if not autoname: autoname = self.autoname
		if not name: name = self.name

		if not autoname and self.get("fields", {"fieldname":"naming_series"}):
			self.autoname = "naming_series:"

		if autoname and (not autoname.startswith('field:')) \
			and (not autoname.startswith('eval:')) \
			and (not autoname.lower() in ('prompt', 'hash')) \
			and (not autoname.startswith('naming_series:')):

			prefix = autoname.split('.')[0]
			used_in = frappe.db.sql('select name from tabDocType where substring_index(autoname, ".", 1) = %s and name!=%s', (prefix, name))
			if used_in:
				frappe.throw(_("Series {0} already used in {1}").format(prefix, used_in[0][0]))

	def on_update(self):
		"""Update database schema, make controller templates if `custom` is not set and clear cache."""
		from frappe.model.db_schema import updatedb
		updatedb(self.name)

		self.change_modified_of_parent()
		make_module_and_roles(self)

		from frappe import conf
		if not self.custom and not (frappe.flags.in_import or frappe.flags.in_test) and conf.get('developer_mode'):
			self.export_doc()
			self.make_controller_template()

		# update index
		if not self.custom:
			self.run_module_method("on_doctype_update")
			if self.flags.in_insert:
				self.run_module_method("after_doctype_insert")

		delete_notification_count_for(doctype=self.name)
		frappe.clear_cache(doctype=self.name)

	def run_module_method(self, method):
		from frappe.modules import load_doctype_module
		module = load_doctype_module(self.name, self.module)
		if hasattr(module, method):
			getattr(module, method)()


	def before_rename(self, old, new, merge=False):
		"""Throw exception if merge. DocTypes cannot be merged."""
		if not self.custom and frappe.session.user != "Administrator":
			frappe.throw(_("DocType can only be renamed by Administrator"))

		self.check_developer_mode()

		if merge:
			frappe.throw(_("DocType can not be merged"))

	def after_rename(self, old, new, merge=False):
		"""Change table name using `RENAME TABLE` if table exists. Or update
		`doctype` property for Single type."""
		if self.issingle:
			frappe.db.sql("""update tabSingles set doctype=%s where doctype=%s""", (new, old))
		else:
			frappe.db.sql("rename table `tab%s` to `tab%s`" % (old, new))

	def before_reload(self):
		"""Preserve naming series changes in Property Setter."""
		if not (self.issingle and self.istable):
			self.preserve_naming_series_options_in_property_setter()

	def preserve_naming_series_options_in_property_setter(self):
		"""Preserve naming_series as property setter if it does not exist"""
		naming_series = self.get("fields", {"fieldname": "naming_series"})

		if not naming_series:
			return

		# check if atleast 1 record exists
		if not (frappe.db.table_exists(self.name) and frappe.db.sql("select name from `tab{}` limit 1".format(self.name))):
			return

		existing_property_setter = frappe.db.get_value("Property Setter", {"doc_type": self.name,
			"property": "options", "field_name": "naming_series"})

		if not existing_property_setter:
			make_property_setter(self.name, "naming_series", "options", naming_series[0].options, "Text", validate_fields_for_doctype=False)
			if naming_series[0].default:
				make_property_setter(self.name, "naming_series", "default", naming_series[0].default, "Text", validate_fields_for_doctype=False)

	def export_doc(self):
		"""Export to standard folder `[module]/doctype/[name]/[name].json`."""
		from frappe.modules.export_file import export_to_files
		export_to_files(record_list=[['DocType', self.name]])

	def import_doc(self):
		"""Import from standard folder `[module]/doctype/[name]/[name].json`."""
		from frappe.modules.import_module import import_from_files
		import_from_files(record_list=[[self.module, 'doctype', self.name]])

	def make_controller_template(self):
		"""Make boilderplate controller template."""
		make_boilerplate("controller.py", self)

		if not (self.istable or self.issingle):
			make_boilerplate("test_controller.py", self)

	def make_amendable(self):
		"""If is_submittable is set, add amended_from docfields."""
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
		"""Returns the highest `idx`"""
		max_idx = frappe.db.sql("""select max(idx) from `tabDocField` where parent = %s""",
			self.name)
		return max_idx and max_idx[0][0] or 0

def validate_fields_for_doctype(doctype):
	validate_fields(frappe.get_meta(doctype, cached=False))

# this is separate because it is also called via custom field
def validate_fields(meta):
	"""Validate doctype fields. Checks

	1. There are no illegal characters in fieldnames
	2. If fieldnames are unique.
	3. Fields that do have database columns are not mandatory.
	4. `Link` and `Table` options are valid.
	5. **Hidden** and **Mandatory** are not set simultaneously.
	7. `Check` type field has default as 0 or 1.
	8. `Dynamic Links` are correctly defined.
	9. Precision is set in numeric fields and is between 1 & 6.
	10. Fold is not at the end (if set).
	11. `search_fields` are valid.
	12. `title_field` and title field pattern are valid.
	13. `unique` check is only valid for Data, Link and Read Only fieldtypes.
	14. `unique` cannot be checked if there exist non-unique values.

	:param meta: `frappe.model.meta.Meta` object to check."""
	def check_illegal_characters(fieldname):
		validate_column_name(fieldname)

	def check_unique_fieldname(fieldname):
		duplicates = filter(None, map(lambda df: df.fieldname==fieldname and str(df.idx) or None, fields))
		if len(duplicates) > 1:
			frappe.throw(_("Fieldname {0} appears multiple times in rows {1}").format(fieldname, ", ".join(duplicates)))

	def check_illegal_mandatory(d):
		if (d.fieldtype in no_value_fields) and d.fieldtype!="Table" and d.reqd:
			frappe.throw(_("Field {0} of type {1} cannot be mandatory").format(d.label, d.fieldtype))

	def check_link_table_options(d):
		if d.fieldtype in ("Link", "Table"):
			if not d.options:
				frappe.throw(_("Options requried for Link or Table type field {0} in row {1}").format(d.label, d.idx))
			if d.options=="[Select]" or d.options==d.parent:
				return
			if d.options != d.parent:
				options = frappe.db.get_value("DocType", d.options, "name")
				if not options:
					frappe.throw(_("Options must be a valid DocType for field {0} in row {1}").format(d.label, d.idx))
				else:
					# fix case
					d.options = options

	def check_hidden_and_mandatory(d):
		if d.hidden and d.reqd and not d.default:
			frappe.throw(_("Field {0} in row {1} cannot be hidden and mandatory without default").format(d.label, d.idx))

	def check_width(d):
		if d.fieldtype == "Currency" and cint(d.width) < 100:
			frappe.throw(_("Max width for type Currency is 100px in row {0}").format(d.idx))

	def check_in_list_view(d):
		if d.in_list_view and d.fieldtype!="Image" and (d.fieldtype in no_value_fields):
			frappe.throw(_("'In List View' not allowed for type {0} in row {1}").format(d.fieldtype, d.idx))

	def check_dynamic_link_options(d):
		if d.fieldtype=="Dynamic Link":
			doctype_pointer = filter(lambda df: df.fieldname==d.options, fields)
			if not doctype_pointer or (doctype_pointer[0].fieldtype not in ("Link", "Select")) \
				or (doctype_pointer[0].fieldtype=="Link" and doctype_pointer[0].options!="DocType"):
				frappe.throw(_("Options 'Dynamic Link' type of field must point to another Link Field with options as 'DocType'"))

	def check_illegal_default(d):
		if d.fieldtype == "Check" and d.default and d.default not in ('0', '1'):
			frappe.throw(_("Default for 'Check' type of field must be either '0' or '1'"))
		if d.fieldtype == "Select" and d.default and (d.default not in d.options.split("\n")):
			frappe.throw(_("Default for {0} must be an option").format(d.fieldname))

	def check_precision(d):
		if d.fieldtype in ("Currency", "Float", "Percent") and d.precision is not None and not (1 <= cint(d.precision) <= 6):
			frappe.throw(_("Precision should be between 1 and 6"))

	def check_unique_and_text(d):
		if getattr(d, "unique", False):
			if d.fieldtype not in ("Data", "Link", "Read Only"):
				frappe.throw(_("Fieldtype {0} for {1} cannot be unique").format(d.fieldtype, d.label))

			has_non_unique_values = frappe.db.sql("""select `{fieldname}`, count(*)
				from `tab{doctype}` group by `{fieldname}` having count(*) > 1 limit 1""".format(
				doctype=d.parent, fieldname=d.fieldname))

			if has_non_unique_values and has_non_unique_values[0][0]:
				frappe.throw(_("Field '{0}' cannot be set as Unique as it has non-unique values").format(d.label))

		if d.search_index and d.fieldtype in ("Text", "Long Text", "Small Text", "Code", "Text Editor"):
			frappe.throw(_("Fieldtype {0} for {1} cannot be indexed").format(d.fieldtype, d.label))

	def check_fold(fields):
		fold_exists = False
		for i, f in enumerate(fields):
			if f.fieldtype=="Fold":
				if fold_exists:
					frappe.throw(_("There can be only one Fold in a form"))
				fold_exists = True
				if i < len(fields)-1:
					nxt = fields[i+1]
					if nxt.fieldtype != "Section Break":
						frappe.throw(_("Fold must come before a Section Break"))
				else:
					frappe.throw(_("Fold can not be at the end of the form"))

	def check_search_fields(meta):
		"""Throw exception if `search_fields` don't contain valid fields."""
		if not meta.search_fields:
			return

		fieldname_list = [d.fieldname for d in fields]
		for fieldname in (meta.search_fields or "").split(","):
			fieldname = fieldname.strip()
			if fieldname not in fieldname_list:
				frappe.throw(_("Search Fields should contain valid fieldnames"))

	def check_title_field(meta):
		"""Throw exception if `title_field` isn't a valid fieldname."""
		if not meta.title_field:
			return

		fieldname_list = [d.fieldname for d in fields]

		if meta.title_field not in fieldname_list:
			frappe.throw(_("Title field must be a valid fieldname"), InvalidFieldNameError)

		def _validate_title_field_pattern(pattern):
			if not pattern:
				return

			for fieldname in re.findall("{(.*?)}", pattern, re.UNICODE):
				if fieldname.startswith("{"):
					# edge case when double curlies are used for escape
					continue

				if fieldname not in fieldname_list:
					frappe.throw(_("{{{0}}} is not a valid fieldname pattern. It should be {{field_name}}.").format(fieldname),
						InvalidFieldNameError)

		df = meta.get("fields", filters={"fieldname": meta.title_field})[0]
		if df:
			_validate_title_field_pattern(df.options)
			_validate_title_field_pattern(df.default)

	fields = meta.get("fields")
	for d in fields:
		if not d.permlevel: d.permlevel = 0
		if not d.fieldname:
			frappe.throw(_("Fieldname is required in row {0}").format(d.idx))
		d.fieldname = d.fieldname.lower()
		check_illegal_characters(d.fieldname)
		check_unique_fieldname(d.fieldname)
		check_illegal_mandatory(d)
		check_link_table_options(d)
		check_dynamic_link_options(d)
		check_hidden_and_mandatory(d)
		check_in_list_view(d)
		check_illegal_default(d)
		check_unique_and_text(d)

	check_fold(fields)
	check_search_fields(meta)
	check_title_field(meta)

def validate_permissions_for_doctype(doctype, for_remove=False):
	"""Validates if permissions are set correctly."""
	doctype = frappe.get_doc("DocType", doctype)

	if frappe.conf.developer_mode and not frappe.flags.in_test:
		# save doctype
		doctype.save()

	else:
		validate_permissions(doctype, for_remove)

		# save permissions
		for perm in doctype.get("permissions"):
			perm.db_update()

def validate_permissions(doctype, for_remove=False):
	permissions = doctype.get("permissions")
	if not permissions:
		frappe.throw(_('Enter at least one permission row'), frappe.MandatoryError)
	issingle = issubmittable = isimportable = False
	if doctype:
		issingle = cint(doctype.issingle)
		issubmittable = cint(doctype.is_submittable)
		isimportable = cint(doctype.allow_import)

	def get_txt(d):
		return _("For {0} at level {1} in {2} in row {3}").format(d.role, d.permlevel, d.parent, d.idx)

	def check_atleast_one_set(d):
		if not d.read and not d.write and not d.submit and not d.cancel and not d.create:
			frappe.throw(_("{0}: No basic permissions set").format(get_txt(d)))

	def check_double(d):
		has_similar = False
		similar_because_of = ""
		for p in permissions:
			if p.role==d.role and p.permlevel==d.permlevel and p!=d:
				if p.apply_user_permissions==d.apply_user_permissions:
					has_similar = True
					similar_because_of = _("Apply User Permissions")
					break
				elif p.if_owner==d.if_owner:
					similar_because_of = _("If Owner")
					has_similar = True
					break

		if has_similar:
			frappe.throw(_("{0}: Only one rule allowed with the same Role, Level and {1}")\
				.format(get_txt(d),	similar_because_of))

	def check_level_zero_is_set(d):
		if cint(d.permlevel) > 0 and d.role != 'All':
			has_zero_perm = False
			for p in permissions:
				if p.role==d.role and (p.permlevel or 0)==0 and p!=d:
					has_zero_perm = True
					break

			if not has_zero_perm:
				frappe.throw(_("{0}: Permission at level 0 must be set before higher levels are set").format(get_txt(d)))

			for invalid in ("create", "submit", "cancel", "amend"):
				if d.get(invalid): d.set(invalid, 0)

	def check_permission_dependency(d):
		if d.cancel and not d.submit:
			frappe.throw(_("{0}: Cannot set Cancel without Submit").format(get_txt(d)))

		if (d.submit or d.cancel or d.amend) and not d.write:
			frappe.throw(_("{0}: Cannot set Submit, Cancel, Amend without Write").format(get_txt(d)))
		if d.amend and not d.write:
			frappe.throw(_("{0}: Cannot set Amend without Cancel").format(get_txt(d)))
		if d.get("import") and not d.create:
			frappe.throw(_("{0}: Cannot set Import without Create").format(get_txt(d)))

	def remove_rights_for_single(d):
		if not issingle:
			return

		if d.report:
			frappe.msgprint(_("Report cannot be set for Single types"))
			d.report = 0
			d.set("import", 0)
			d.set("export", 0)

		for ptype, label in (
			("set_user_permissions", _("Set User Permissions")),
			("apply_user_permissions", _("Apply User Permissions"))):
			if d.get(ptype):
				d.set(ptype, 0)
				frappe.msgprint(_("{0} cannot be set for Single types").format(label))

	def check_if_submittable(d):
		if d.submit and not issubmittable:
			frappe.throw(_("{0}: Cannot set Assign Submit if not Submittable").format(get_txt(d)))
		elif d.amend and not issubmittable:
			frappe.throw(_("{0}: Cannot set Assign Amend if not Submittable").format(get_txt(d)))

	def check_if_importable(d):
		if d.get("import") and not isimportable:
			frappe.throw(_("{0}: Cannot set import as {1} is not importable").format(get_txt(d), doctype))

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
	"""Make `Module Def` and `Role` records if already not made. Called while installing."""
	try:
		if not frappe.db.exists("Module Def", doc.module):
			m = frappe.get_doc({"doctype": "Module Def", "module_name": doc.module})
			m.app_name = frappe.local.module_app[frappe.scrub(doc.module)]
			m.flags.ignore_mandatory = m.flags.ignore_permissions = True
			m.insert()

		default_roles = ["Administrator", "Guest", "All"]
		roles = [p.role for p in doc.get("permissions") or []] + default_roles

		for role in list(set(roles)):
			if not frappe.db.exists("Role", role):
				r = frappe.get_doc({"doctype": "Role", "role_name": role})
				r.role_name = role
				r.flags.ignore_mandatory = r.flags.ignore_permissions = True
				r.insert()
	except frappe.DoesNotExistError, e:
		pass
	except frappe.SQLError, e:
		if e.args[0]==1146:
			pass
		else:
			raise

def init_list(doctype):
	"""Make boilerplate list views."""
	doc = frappe.get_meta(doctype)
	make_boilerplate("controller_list.js", doc)
	make_boilerplate("controller_list.html", doc)
