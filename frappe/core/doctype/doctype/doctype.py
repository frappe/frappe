# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import copy
import json
import os

# imports - standard imports
import re
import shutil
from typing import TYPE_CHECKING, Union

# imports - module imports
import frappe
from frappe import _
from frappe.cache_manager import clear_controller_cache, clear_user_cache
from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.database.schema import validate_column_length, validate_column_name
from frappe.desk.notifications import delete_notification_count_for, get_filters_for
from frappe.desk.utils import validate_route_conflict
from frappe.model import (
	child_table_fields,
	data_field_options,
	default_fields,
	no_value_fields,
	table_fields,
)
from frappe.model.base_document import get_controller
from frappe.model.docfield import supports_translation
from frappe.model.document import Document
from frappe.model.meta import Meta
from frappe.modules import get_doc_path, make_boilerplate
from frappe.modules.import_file import get_file_path
from frappe.query_builder.functions import Concat
from frappe.utils import cint, random_string
from frappe.website.utils import clear_cache

if TYPE_CHECKING:
	from frappe.custom.doctype.customize_form.customize_form import CustomizeForm

DEPENDS_ON_PATTERN = re.compile(r'[\w\.:_]+\s*={1}\s*[\w\.@\'"]+')
ILLEGAL_FIELDNAME_PATTERN = re.compile("""['",./%@()<>{}]""")
WHITESPACE_PADDING_PATTERN = re.compile(r"^[ \t\n\r]+|[ \t\n\r]+$", flags=re.ASCII)
START_WITH_LETTERS_PATTERN = re.compile(r"^(?![\W])[^\d_\s][\w -]+$", flags=re.ASCII)
FIELD_PATTERN = re.compile("{(.*?)}", flags=re.UNICODE)


class InvalidFieldNameError(frappe.ValidationError):
	pass


class UniqueFieldnameError(frappe.ValidationError):
	pass


class IllegalMandatoryError(frappe.ValidationError):
	pass


class DoctypeLinkError(frappe.ValidationError):
	pass


class WrongOptionsDoctypeLinkError(frappe.ValidationError):
	pass


class HiddenAndMandatoryWithoutDefaultError(frappe.ValidationError):
	pass


class NonUniqueError(frappe.ValidationError):
	pass


class CannotIndexedError(frappe.ValidationError):
	pass


class CannotCreateStandardDoctypeError(frappe.ValidationError):
	pass


form_grid_templates = {"fields": "templates/form_grid/fields.html"}


class DocType(Document):
	def get_feed(self):
		return self.name

	def validate(self):
		"""Validate DocType before saving.

		- Check if developer mode is set.
		- Validate series
		- Check fieldnames (duplication etc)
		- Clear permission table for child tables
		- Add `amended_from` and `amended_by` if Amendable
		- Add custom field `auto_repeat` if Repeatable
		- Check if links point to valid fieldnames"""

		self.check_developer_mode()

		self.validate_name()

		self.set_defaults_for_single_and_table()
		self.set_defaults_for_autoincremented()
		self.scrub_field_names()
		self.set_default_in_list_view()
		self.set_default_translatable()
		validate_series(self)
		self.set("can_change_name_type", validate_autoincrement_autoname(self))
		self.validate_document_type()
		validate_fields(self)

		if not self.istable:
			validate_permissions(self)

		self.make_amendable()
		self.make_repeatable()
		self.validate_nestedset()
		self.validate_child_table()
		self.validate_website()
		self.ensure_minimum_max_attachment_limit()
		validate_links_table_fieldnames(self)

		if not self.is_new():
			self.before_update = frappe.get_doc("DocType", self.name)
			self.setup_fields_to_fetch()
			self.validate_field_name_conflicts()

		check_email_append_to(self)

		if self.default_print_format and not self.custom:
			frappe.throw(_("Standard DocType cannot have default print format, use Customize Form"))

	def validate_field_name_conflicts(self):
		"""Check if field names dont conflict with controller properties and methods"""
		core_doctypes = [
			"Custom DocPerm",
			"DocPerm",
			"Custom Field",
			"Customize Form Field",
			"DocField",
		]

		if self.name in core_doctypes:
			return

		try:
			controller = get_controller(self.name)
		except ImportError:
			controller = Document

		available_objects = {x for x in dir(controller) if isinstance(x, str)}
		property_set = {x for x in available_objects if is_a_property(getattr(controller, x, None))}
		method_set = {
			x for x in available_objects if x not in property_set and callable(getattr(controller, x, None))
		}

		for docfield in self.get("fields") or []:
			if docfield.fieldtype in no_value_fields:
				continue

			conflict_type = None
			field = docfield.fieldname
			field_label = docfield.label or docfield.fieldname

			if docfield.fieldname in method_set:
				conflict_type = "controller method"
			if docfield.fieldname in property_set and not docfield.is_virtual:
				conflict_type = "class property"

			if conflict_type:
				frappe.throw(
					_("Fieldname '{0}' conflicting with a {1} of the name {2} in {3}").format(
						field_label, conflict_type, field, self.name
					)
				)

	def set_defaults_for_single_and_table(self):
		if self.issingle:
			self.allow_import = 0
			self.is_submittable = 0
			self.istable = 0

		elif self.istable:
			self.allow_import = 0
			self.permissions = []

	def set_defaults_for_autoincremented(self):
		if self.autoname and self.autoname == "autoincrement":
			self.allow_rename = 0

	def set_default_in_list_view(self):
		"""Set default in-list-view for first 4 mandatory fields"""
		not_allowed_in_list_view = get_fields_not_allowed_in_list_view(self.meta)

		if not [d.fieldname for d in self.fields if d.in_list_view]:
			cnt = 0
			for d in self.fields:
				if d.reqd and not d.hidden and not d.fieldtype in not_allowed_in_list_view:
					d.in_list_view = 1
					cnt += 1
					if cnt == 4:
						break

	def set_default_translatable(self):
		"""Ensure that non-translatable never will be translatable"""
		for d in self.fields:
			if d.translatable and not supports_translation(d.fieldtype):
				d.translatable = 0

	def check_developer_mode(self):
		"""Throw exception if not developer mode or via patch"""
		if frappe.flags.in_patch or frappe.flags.in_test:
			return

		if not frappe.conf.get("developer_mode") and not self.custom:
			frappe.throw(
				_("Not in Developer Mode! Set in site_config.json or make 'Custom' DocType."),
				CannotCreateStandardDoctypeError,
			)

		if self.is_virtual and self.custom:
			frappe.throw(
				_("Not allowed to create custom Virtual DocType."), CannotCreateStandardDoctypeError
			)

		if frappe.conf.get("developer_mode"):
			self.owner = "Administrator"
			self.modified_by = "Administrator"

	def setup_fields_to_fetch(self):
		"""Setup query to update values for newly set fetch values"""
		try:
			old_meta = frappe.get_meta(frappe.get_doc("DocType", self.name), cached=False)
			old_fields_to_fetch = [df.fieldname for df in old_meta.get_fields_to_fetch()]
		except frappe.DoesNotExistError:
			old_fields_to_fetch = []

		new_meta = frappe.get_meta(self, cached=False)

		self.flags.update_fields_to_fetch_queries = []

		if set(old_fields_to_fetch) != {df.fieldname for df in new_meta.get_fields_to_fetch()}:
			for df in new_meta.get_fields_to_fetch():
				if df.fieldname not in old_fields_to_fetch:
					link_fieldname, source_fieldname = df.fetch_from.split(".", 1)
					link_df = new_meta.get_field(link_fieldname)

					if frappe.db.db_type == "postgres":
						update_query = """
							UPDATE `tab{doctype}`
							SET `{fieldname}` = source.`{source_fieldname}`
							FROM `tab{link_doctype}` as source
							WHERE `{link_fieldname}` = source.name
							AND ifnull(`{fieldname}`, '')=''
						"""
					else:
						update_query = """
							UPDATE `tab{doctype}` as target
							INNER JOIN `tab{link_doctype}` as source
							ON `target`.`{link_fieldname}` = `source`.`name`
							SET `target`.`{fieldname}` = `source`.`{source_fieldname}`
							WHERE ifnull(`target`.`{fieldname}`, '')=""
						"""

					self.flags.update_fields_to_fetch_queries.append(
						update_query.format(
							link_doctype=link_df.options,
							source_fieldname=source_fieldname,
							doctype=self.name,
							fieldname=df.fieldname,
							link_fieldname=link_fieldname,
						)
					)

	def update_fields_to_fetch(self):
		"""Update fetch values based on queries setup"""
		if self.flags.update_fields_to_fetch_queries and not self.issingle:
			for query in self.flags.update_fields_to_fetch_queries:
				frappe.db.sql(query)

	def validate_document_type(self):
		if self.document_type == "Transaction":
			self.document_type = "Document"
		if self.document_type == "Master":
			self.document_type = "Setup"

	def validate_website(self):
		"""Ensure that website generator has field 'route'"""
		if self.route:
			self.route = self.route.strip("/")

		if self.has_web_view:
			# route field must be present
			if not "route" in [d.fieldname for d in self.fields]:
				frappe.throw(_('Field "route" is mandatory for Web Views'), title="Missing Field")

			# clear website cache
			clear_cache()

	def ensure_minimum_max_attachment_limit(self):
		"""Ensure that max_attachments is *at least* bigger than number of attach fields."""
		from frappe.model import attachment_fieldtypes

		if not self.max_attachments:
			return

		total_attach_fields = len([d for d in self.fields if d.fieldtype in attachment_fieldtypes])
		if total_attach_fields > self.max_attachments:
			self.max_attachments = total_attach_fields
			field_label = frappe.bold(self.meta.get_field("max_attachments").label)
			frappe.msgprint(
				_("Number of attachment fields are more than {}, limit updated to {}.").format(
					field_label, total_attach_fields
				),
				title=_("Insufficient attachment limit"),
				alert=True,
			)

	def change_modified_of_parent(self):
		"""Change the timestamp of parent DocType if the current one is a child to clear caches."""
		if frappe.flags.in_import:
			return
		parent_list = frappe.get_all(
			"DocField", "parent", dict(fieldtype=["in", frappe.model.table_fields], options=self.name)
		)
		for p in parent_list:
			frappe.db.update("DocType", p.parent, {}, for_update=False)

	def scrub_field_names(self):
		"""Sluggify fieldnames if not set from Label."""
		restricted = (
			"name",
			"parent",
			"creation",
			"owner",
			"modified",
			"modified_by",
			"parentfield",
			"parenttype",
			"file_list",
			"flags",
			"docstatus",
		)
		for d in self.get("fields"):
			if d.fieldtype:
				if not getattr(d, "fieldname", None):
					if d.label:
						d.fieldname = d.label.strip().lower().replace(" ", "_").strip("?")
						if d.fieldname in restricted:
							d.fieldname = d.fieldname + "1"
						if d.fieldtype == "Section Break":
							d.fieldname = d.fieldname + "_section"
						elif d.fieldtype == "Column Break":
							d.fieldname = d.fieldname + "_column"
						elif d.fieldtype == "Tab Break":
							d.fieldname = d.fieldname + "_tab"
					elif d.fieldtype in ("Section Break", "Column Break", "Tab Break"):
						d.fieldname = d.fieldtype.lower().replace(" ", "_") + "_" + str(random_string(5))
					else:
						frappe.throw(_("Row #{}: Fieldname is required").format(d.idx), title="Missing Fieldname")
				else:
					if d.fieldname in restricted:
						frappe.throw(_("Fieldname {0} is restricted").format(d.fieldname), InvalidFieldNameError)
				d.fieldname = ILLEGAL_FIELDNAME_PATTERN.sub("", d.fieldname)

				# fieldnames should be lowercase
				d.fieldname = d.fieldname.lower()

			# unique is automatically an index
			if d.unique:
				d.search_index = 0

	def on_update(self):
		"""Update database schema, make controller templates if `custom` is not set and clear cache."""

		if self.get("can_change_name_type"):
			self.setup_autoincrement_and_sequence()

		try:
			frappe.db.updatedb(self.name, Meta(self))
		except Exception as e:
			print(f"\n\nThere was an issue while migrating the DocType: {self.name}\n")
			raise e

		self.change_modified_of_parent()
		make_module_and_roles(self)

		self.update_fields_to_fetch()

		allow_doctype_export = (
			not self.custom
			and not frappe.flags.in_import
			and (frappe.conf.developer_mode or frappe.flags.allow_doctype_export)
		)
		if allow_doctype_export:
			self.export_doc()
			self.make_controller_template()
			self.set_base_class_for_controller()

		# update index
		if not self.custom:
			self.run_module_method("on_doctype_update")
			if self.flags.in_insert:
				self.run_module_method("after_doctype_insert")

		delete_notification_count_for(doctype=self.name)
		frappe.clear_cache(doctype=self.name)

		# clear user cache so that on the next reload this doctype is included in boot
		clear_user_cache(frappe.session.user)

		if not frappe.flags.in_install and hasattr(self, "before_update"):
			self.sync_global_search()

		clear_linked_doctype_cache()

	def setup_autoincrement_and_sequence(self):
		"""Changes name type and makes sequence on change (if required)"""

		name_type = f"varchar({frappe.db.VARCHAR_LEN})"

		if self.autoname == "autoincrement":
			name_type = "bigint"
			frappe.db.create_sequence(self.name, check_not_exists=True, cache=frappe.db.SEQUENCE_CACHE)

		change_name_column_type(self.name, name_type)

	def sync_global_search(self):
		"""If global search settings are changed, rebuild search properties for this table"""
		global_search_fields_before_update = [
			d.fieldname for d in self.before_update.fields if d.in_global_search
		]
		if self.before_update.show_name_in_global_search:
			global_search_fields_before_update.append("name")

		global_search_fields_after_update = [d.fieldname for d in self.fields if d.in_global_search]
		if self.show_name_in_global_search:
			global_search_fields_after_update.append("name")

		if set(global_search_fields_before_update) != set(global_search_fields_after_update):
			now = (not frappe.request) or frappe.flags.in_test or frappe.flags.in_install
			frappe.enqueue("frappe.utils.global_search.rebuild_for_doctype", now=now, doctype=self.name)

	def set_base_class_for_controller(self):
		"""If DocType.has_web_view has been changed, updates the controller class and import
		from `WebsiteGenertor` to `Document` or viceversa"""

		if not self.has_value_changed("has_web_view"):
			return

		despaced_name = self.name.replace(" ", "_")
		scrubbed_name = frappe.scrub(self.name)
		scrubbed_module = frappe.scrub(self.module)
		controller_path = frappe.get_module_path(
			scrubbed_module, "doctype", scrubbed_name, f"{scrubbed_name}.py"
		)

		document_cls_tag = f"class {despaced_name}(Document)"
		document_import_tag = "from frappe.model.document import Document"
		website_generator_cls_tag = f"class {despaced_name}(WebsiteGenerator)"
		website_generator_import_tag = "from frappe.website.website_generator import WebsiteGenerator"

		with open(controller_path) as f:
			code = f.read()
		updated_code = code

		is_website_generator_class = all(
			[website_generator_cls_tag in code, website_generator_import_tag in code]
		)

		if self.has_web_view and not is_website_generator_class:
			updated_code = updated_code.replace(document_import_tag, website_generator_import_tag).replace(
				document_cls_tag, website_generator_cls_tag
			)
		elif not self.has_web_view and is_website_generator_class:
			updated_code = updated_code.replace(website_generator_import_tag, document_import_tag).replace(
				website_generator_cls_tag, document_cls_tag
			)

		if updated_code != code:
			with open(controller_path, "w") as f:
				f.write(updated_code)

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
		self.validate_name(new)

		if merge:
			frappe.throw(_("DocType can not be merged"))

	def after_rename(self, old, new, merge=False):
		"""Change table name using `RENAME TABLE` if table exists. Or update
		`doctype` property for Single type."""

		if self.issingle:
			frappe.db.sql("""update tabSingles set doctype=%s where doctype=%s""", (new, old))
			frappe.db.sql(
				"""update tabSingles set value=%s
				where doctype=%s and field='name' and value = %s""",
				(new, new, old),
			)
		else:
			frappe.db.rename_table(old, new)
			frappe.db.commit()

		# Do not rename and move files and folders for custom doctype
		if not self.custom:
			if not frappe.flags.in_patch:
				self.rename_files_and_folders(old, new)

			clear_controller_cache(old)

	def after_delete(self):
		if not self.custom:
			clear_controller_cache(self.name)

	def rename_files_and_folders(self, old, new):
		# move files
		new_path = get_doc_path(self.module, "doctype", new)
		old_path = get_doc_path(self.module, "doctype", old)
		shutil.move(old_path, new_path)

		# rename files
		for fname in os.listdir(new_path):
			if frappe.scrub(old) in fname:
				old_file_name = os.path.join(new_path, fname)
				new_file_name = os.path.join(new_path, fname.replace(frappe.scrub(old), frappe.scrub(new)))
				shutil.move(old_file_name, new_file_name)

		self.rename_inside_controller(new, old, new_path)
		frappe.msgprint(_("Renamed files and replaced code in controllers, please check!"))

	def rename_inside_controller(self, new, old, new_path):
		for fname in ("{}.js", "{}.py", "{}_list.js", "{}_calendar.js", "test_{}.py", "test_{}.js"):
			fname = os.path.join(new_path, fname.format(frappe.scrub(new)))
			if os.path.exists(fname):
				with open(fname) as f:
					code = f.read()
				with open(fname, "w") as f:
					if fname.endswith(".js"):
						file_content = code.replace(old, new)  # replace str with full str (js controllers)

					elif fname.endswith(".py"):
						file_content = code.replace(
							frappe.scrub(old), frappe.scrub(new)
						)  # replace str with _ (py imports)
						file_content = file_content.replace(
							old.replace(" ", ""), new.replace(" ", "")
						)  # replace str (py controllers)

					f.write(file_content)

		# updating json file with new name
		doctype_json_path = os.path.join(new_path, f"{frappe.scrub(new)}.json")
		current_data = frappe.get_file_json(doctype_json_path)
		current_data["name"] = new

		with open(doctype_json_path, "w") as f:
			json.dump(current_data, f, indent=1)

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
		if not (
			frappe.db.table_exists(self.name)
			and frappe.get_all(self.name, fields=["name"], limit=1, as_list=True)
		):
			return

		existing_property_setter = frappe.db.get_value(
			"Property Setter", {"doc_type": self.name, "property": "options", "field_name": "naming_series"}
		)

		if not existing_property_setter:
			make_property_setter(
				self.name,
				"naming_series",
				"options",
				naming_series[0].options,
				"Text",
				validate_fields_for_doctype=False,
			)
			if naming_series[0].default:
				make_property_setter(
					self.name,
					"naming_series",
					"default",
					naming_series[0].default,
					"Text",
					validate_fields_for_doctype=False,
				)

	def before_export(self, docdict):
		# remove null and empty fields
		def remove_null_fields(o):
			to_remove = []
			for attr, value in o.items():
				if isinstance(value, list):
					for v in value:
						remove_null_fields(v)
				elif not value:
					to_remove.append(attr)

			for attr in to_remove:
				del o[attr]

		remove_null_fields(docdict)

		# retain order of 'fields' table and change order in 'field_order'
		docdict["field_order"] = [f.fieldname for f in self.fields]

		if self.custom:
			return

		path = get_file_path(self.module, "DocType", self.name)
		if os.path.exists(path):
			try:
				with open(path) as txtfile:
					olddoc = json.loads(txtfile.read())

				old_field_names = [f["fieldname"] for f in olddoc.get("fields", [])]
				if old_field_names:
					new_field_dicts = []
					remaining_field_names = [f.fieldname for f in self.fields]

					for fieldname in old_field_names:
						field_dict = [f for f in docdict["fields"] if f["fieldname"] == fieldname]
						if field_dict:
							new_field_dicts.append(field_dict[0])
							if fieldname in remaining_field_names:
								remaining_field_names.remove(fieldname)

					for fieldname in remaining_field_names:
						field_dict = [f for f in docdict["fields"] if f["fieldname"] == fieldname]
						new_field_dicts.append(field_dict[0])

					docdict["fields"] = new_field_dicts
			except ValueError:
				pass

	@staticmethod
	def prepare_for_import(docdict):
		# set order of fields from field_order
		if docdict.get("field_order"):
			new_field_dicts = []
			remaining_field_names = [f["fieldname"] for f in docdict.get("fields", [])]

			for fieldname in docdict.get("field_order"):
				field_dict = [f for f in docdict.get("fields", []) if f["fieldname"] == fieldname]
				if field_dict:
					new_field_dicts.append(field_dict[0])
					if fieldname in remaining_field_names:
						remaining_field_names.remove(fieldname)

			for fieldname in remaining_field_names:
				field_dict = [f for f in docdict.get("fields", []) if f["fieldname"] == fieldname]
				new_field_dicts.append(field_dict[0])

			docdict["fields"] = new_field_dicts

		if "field_order" in docdict:
			del docdict["field_order"]

	def export_doc(self):
		"""Export to standard folder `[module]/doctype/[name]/[name].json`."""
		from frappe.modules.export_file import export_to_files

		export_to_files(record_list=[["DocType", self.name]], create_init=True)

	def make_controller_template(self):
		"""Make boilerplate controller template."""
		make_boilerplate("controller._py", self)

		if not self.istable:
			make_boilerplate("test_controller._py", self.as_dict())
			make_boilerplate("controller.js", self.as_dict())
			# make_boilerplate("controller_list.js", self.as_dict())

		if self.has_web_view:
			templates_path = frappe.get_module_path(
				frappe.scrub(self.module), "doctype", frappe.scrub(self.name), "templates"
			)
			if not os.path.exists(templates_path):
				os.makedirs(templates_path)
			make_boilerplate("templates/controller.html", self.as_dict())
			make_boilerplate("templates/controller_row.html", self.as_dict())

	def make_amendable(self):
		"""If is_submittable is set, add amended_from docfields."""
		if self.is_submittable:
			docfield_exists = frappe.get_all(
				"DocField", filters={"fieldname": "amended_from", "parent": self.name}, pluck="name", limit=1
			)
			if not docfield_exists:
				self.append(
					"fields",
					{
						"label": "Amended From",
						"fieldtype": "Link",
						"fieldname": "amended_from",
						"options": self.name,
						"read_only": 1,
						"print_hide": 1,
						"no_copy": 1,
					},
				)

	def make_repeatable(self):
		"""If allow_auto_repeat is set, add auto_repeat custom field."""
		if self.allow_auto_repeat:
			if not frappe.db.exists(
				"Custom Field", {"fieldname": "auto_repeat", "dt": self.name}
			) and not frappe.db.exists(
				"DocField", {"fieldname": "auto_repeat", "parent": self.name}
			):
				insert_after = self.fields[len(self.fields) - 1].fieldname
				df = dict(
					fieldname="auto_repeat",
					label="Auto Repeat",
					fieldtype="Link",
					options="Auto Repeat",
					insert_after=insert_after,
					read_only=1,
					no_copy=1,
					print_hide=1,
				)
				create_custom_field(self.name, df)

	def validate_nestedset(self):
		if not self.get("is_tree"):
			return
		self.add_nestedset_fields()

		if not self.nsm_parent_field:
			field_label = frappe.bold(_("Parent Field (Tree)"))
			frappe.throw(_("{0} is a mandatory field").format(field_label), frappe.MandatoryError)

		# check if field is valid
		fieldnames = [df.fieldname for df in self.fields]
		if self.nsm_parent_field and self.nsm_parent_field not in fieldnames:
			frappe.throw(_("Parent Field must be a valid fieldname"), InvalidFieldNameError)

	def add_nestedset_fields(self):
		"""If is_tree is set, add parent_field, lft, rgt, is_group fields."""
		fieldnames = [df.fieldname for df in self.fields]
		if "lft" in fieldnames:
			return

		self.append(
			"fields",
			{
				"label": "Left",
				"fieldtype": "Int",
				"fieldname": "lft",
				"read_only": 1,
				"hidden": 1,
				"no_copy": 1,
			},
		)

		self.append(
			"fields",
			{
				"label": "Right",
				"fieldtype": "Int",
				"fieldname": "rgt",
				"read_only": 1,
				"hidden": 1,
				"no_copy": 1,
			},
		)

		self.append("fields", {"label": "Is Group", "fieldtype": "Check", "fieldname": "is_group"})
		self.append(
			"fields",
			{"label": "Old Parent", "fieldtype": "Link", "options": self.name, "fieldname": "old_parent"},
		)

		parent_field_label = f"Parent {self.name}"
		parent_field_name = frappe.scrub(parent_field_label)
		self.append(
			"fields",
			{
				"label": parent_field_label,
				"fieldtype": "Link",
				"options": self.name,
				"fieldname": parent_field_name,
			},
		)
		self.nsm_parent_field = parent_field_name

	def validate_child_table(self):
		if not self.get("istable") or self.is_new() or self.get("is_virtual"):
			# if the doctype is not a child table then return
			# if the doctype is a new doctype and also a child table then
			# don't move forward as it will be handled via schema
			return

		self.add_child_table_fields()

	def add_child_table_fields(self):
		from frappe.database.schema import add_column

		add_column(self.name, "parent", "Data")
		add_column(self.name, "parenttype", "Data")
		add_column(self.name, "parentfield", "Data")

	def get_max_idx(self):
		"""Returns the highest `idx`"""
		max_idx = frappe.db.sql("""select max(idx) from `tabDocField` where parent = %s""", self.name)
		return max_idx and max_idx[0][0] or 0

	def validate_name(self, name=None):
		if not name:
			name = self.name

		# a Doctype name is the tablename created in database
		# `tab<Doctype Name>` the length of tablename is limited to 64 characters
		max_length = frappe.db.MAX_COLUMN_LENGTH - 3
		if len(name) > max_length:
			# length(tab + <Doctype Name>) should be equal to 64 characters hence doctype should be 61 characters
			frappe.throw(
				_("Doctype name is limited to {0} characters ({1})").format(max_length, name), frappe.NameError
			)

		# a DocType name should not start or end with an empty space
		if WHITESPACE_PADDING_PATTERN.search(name):
			frappe.throw(_("DocType's name should not start or end with whitespace"), frappe.NameError)

		# a DocType's name should not start with a number or underscore
		# and should only contain letters, numbers, underscore, and hyphen
		if not START_WITH_LETTERS_PATTERN.match(name):
			frappe.throw(
				_(
					"A DocType's name should start with a letter and can only "
					"consist of letters, numbers, spaces, underscores and hyphens"
				),
				frappe.NameError,
				title="Invalid Name",
			)

		validate_route_conflict(self.doctype, self.name)


def validate_series(dt, autoname=None, name=None):
	"""Validate if `autoname` property is correctly set."""
	if not autoname:
		autoname = dt.autoname
	if not name:
		name = dt.name

	if not autoname and dt.get("fields", {"fieldname": "naming_series"}):
		dt.autoname = "naming_series:"
	elif dt.autoname and dt.autoname.startswith("naming_series:"):
		fieldname = dt.autoname.split("naming_series:", 1)[0] or "naming_series"
		if not dt.get("fields", {"fieldname": fieldname}):
			frappe.throw(
				_("Fieldname called {0} must exist to enable autonaming").format(frappe.bold(fieldname)),
				title=_("Field Missing"),
			)

	# validate field name if autoname field:fieldname is used
	# Create unique index on autoname field automatically.
	if autoname and autoname.startswith("field:"):
		field = autoname.split(":")[1]
		if not field or field not in [df.fieldname for df in dt.fields]:
			frappe.throw(_("Invalid fieldname '{0}' in autoname").format(field))
		else:
			for df in dt.fields:
				if df.fieldname == field:
					df.unique = 1
					break

	if (
		autoname
		and (not autoname.startswith("field:"))
		and (not autoname.startswith("eval:"))
		and (autoname.lower() not in ("prompt", "hash"))
		and (not autoname.startswith("naming_series:"))
		and (not autoname.startswith("format:"))
	):

		prefix = autoname.split(".", 1)[0]
		doctype = frappe.qb.DocType("DocType")
		used_in = (
			frappe.qb.from_(doctype)
			.select(doctype.name)
			.where(doctype.autoname.like(Concat(prefix, ".%")))
			.where(doctype.name != name)
		).run()
		if used_in:
			frappe.throw(_("Series {0} already used in {1}").format(prefix, used_in[0][0]))


def validate_autoincrement_autoname(dt: Union[DocType, "CustomizeForm"]) -> bool:
	"""Checks if can doctype can change to/from autoincrement autoname"""

	def get_autoname_before_save(dt: Union[DocType, "CustomizeForm"]) -> str:
		if dt.doctype == "Customize Form":
			property_value = frappe.db.get_value(
				"Property Setter", {"doc_type": dt.doc_type, "property": "autoname"}, "value"
			)
			# initially no property setter is set,
			# hence getting autoname value from the doctype itself
			if not property_value:
				return frappe.db.get_value("DocType", dt.doc_type, "autoname") or ""

			return property_value

		return getattr(dt.get_doc_before_save(), "autoname", "")

	if not dt.is_new():
		autoname_before_save = get_autoname_before_save(dt)
		is_autoname_autoincrement = dt.autoname == "autoincrement"

		if (
			is_autoname_autoincrement
			and autoname_before_save != "autoincrement"
			or (not is_autoname_autoincrement and autoname_before_save == "autoincrement")
		):

			if dt.doctype == "Customize Form":
				frappe.throw(_("Cannot change to/from autoincrement autoname in Customize Form"))

			if frappe.get_meta(dt.name).issingle:
				return False

			if not frappe.get_all(dt.name, limit=1):
				# allow changing the column type if there is no data
				return True

			frappe.throw(
				_("Can only change to/from Autoincrement naming rule when there is no data in the doctype")
			)

	return False


def change_name_column_type(doctype_name: str, type: str) -> None:
	"""Changes name column type"""

	args = (
		(doctype_name, "name", type, False, True)
		if (frappe.db.db_type == "postgres")
		else (doctype_name, "name", type, True)
	)

	frappe.db.change_column_type(*args)


def validate_links_table_fieldnames(meta):
	"""Validate fieldnames in Links table"""
	if not meta.links or frappe.flags.in_patch or frappe.flags.in_fixtures or frappe.flags.in_migrate:
		return

	fieldnames = tuple(field.fieldname for field in meta.fields)
	for index, link in enumerate(meta.links, 1):
		_test_connection_query(doctype=link.link_doctype, field=link.link_fieldname, idx=index)

		if not link.is_child_table:
			continue

		if not link.parent_doctype:
			message = _("Document Links Row #{0}: Parent DocType is mandatory for internal links").format(
				index
			)
			frappe.throw(message, frappe.ValidationError, _("Parent Missing"))

		if not link.table_fieldname:
			message = _("Document Links Row #{0}: Table Fieldname is mandatory for internal links").format(
				index
			)
			frappe.throw(message, frappe.ValidationError, _("Table Fieldname Missing"))

		if meta.name == link.parent_doctype:
			field_exists = link.table_fieldname in fieldnames
		else:
			field_exists = frappe.get_meta(link.parent_doctype).has_field(link.table_fieldname)

		if not field_exists:
			message = _("Document Links Row #{0}: Could not find field {1} in {2} DocType").format(
				index, frappe.bold(link.table_fieldname), frappe.bold(meta.name)
			)
			frappe.throw(message, frappe.ValidationError, _("Invalid Table Fieldname"))


def _test_connection_query(doctype, field, idx):
	"""Make sure that connection can be queried.

	This function executes query similar to one that would be executed for
	finding count on dashboard and hence validates if fieldname/doctype are
	correct.
	"""
	filters = get_filters_for(doctype) or {}
	filters[field] = ""

	try:
		frappe.get_all(doctype, filters=filters, limit=1, distinct=True, ignore_ifnull=True)
	except Exception as e:
		frappe.clear_last_message()
		msg = _("Document Links Row #{0}: Invalid doctype or fieldname.").format(idx)
		msg += "<br>" + str(e)
		frappe.throw(msg, InvalidFieldNameError)


def validate_fields_for_doctype(doctype):
	meta = frappe.get_meta(doctype, cached=False)
	validate_links_table_fieldnames(meta)
	validate_fields(meta)


# this is separate because it is also called via custom field
def validate_fields(meta):
	"""Validate doctype fields. Checks
	1. There are no illegal characters in fieldnames
	2. If fieldnames are unique.
	3. Validate column length.
	4. Fields that do have database columns are not mandatory.
	5. `Link` and `Table` options are valid.
	6. **Hidden** and **Mandatory** are not set simultaneously.
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

	def check_invalid_fieldnames(docname, fieldname):
		if fieldname in Document._reserved_keywords:
			frappe.throw(
				_("{0}: fieldname cannot be set to reserved keyword {1}").format(
					frappe.bold(docname),
					frappe.bold(fieldname),
				),
				title=_("Invalid Fieldname"),
			)

	def check_unique_fieldname(docname, fieldname):
		duplicates = list(
			filter(None, map(lambda df: df.fieldname == fieldname and str(df.idx) or None, fields))
		)
		if len(duplicates) > 1:
			frappe.throw(
				_("{0}: Fieldname {1} appears multiple times in rows {2}").format(
					docname, fieldname, ", ".join(duplicates)
				),
				UniqueFieldnameError,
			)

	def check_fieldname_length(fieldname):
		validate_column_length(fieldname)

	def check_illegal_mandatory(docname, d):
		if (d.fieldtype in no_value_fields) and d.fieldtype not in table_fields and d.reqd:
			frappe.throw(
				_("{0}: Field {1} of type {2} cannot be mandatory").format(docname, d.label, d.fieldtype),
				IllegalMandatoryError,
			)

	def check_link_table_options(docname, d):
		if frappe.flags.in_patch or frappe.flags.in_fixtures:
			return

		if d.fieldtype in ("Link",) + table_fields:
			if not d.options:
				frappe.throw(
					_("{0}: Options required for Link or Table type field {1} in row {2}").format(
						docname, d.label, d.idx
					),
					DoctypeLinkError,
				)
			if d.options == "[Select]" or d.options == d.parent:
				return
			if d.options != d.parent:
				options = frappe.db.get_value("DocType", d.options, "name")
				if not options:
					frappe.throw(
						_("{0}: Options must be a valid DocType for field {1} in row {2}").format(
							docname, d.label, d.idx
						),
						WrongOptionsDoctypeLinkError,
					)
				elif not (options == d.options):
					frappe.throw(
						_("{0}: Options {1} must be the same as doctype name {2} for the field {3}").format(
							docname, d.options, options, d.label
						),
						DoctypeLinkError,
					)
				else:
					# fix case
					d.options = options

	def check_hidden_and_mandatory(docname, d):
		if d.hidden and d.reqd and not d.default and not frappe.flags.in_migrate:
			frappe.throw(
				_("{0}: Field {1} in row {2} cannot be hidden and mandatory without default").format(
					docname, d.label, d.idx
				),
				HiddenAndMandatoryWithoutDefaultError,
			)

	def check_width(d):
		if d.fieldtype == "Currency" and cint(d.width) < 100:
			frappe.throw(_("Max width for type Currency is 100px in row {0}").format(d.idx))

	def check_in_list_view(is_table, d):
		if d.in_list_view and (d.fieldtype in not_allowed_in_list_view):
			property_label = "In Grid View" if is_table else "In List View"
			frappe.throw(
				_("'{0}' not allowed for type {1} in row {2}").format(property_label, d.fieldtype, d.idx)
			)

	def check_in_global_search(d):
		if d.in_global_search and d.fieldtype in no_value_fields:
			frappe.throw(
				_("'In Global Search' not allowed for type {0} in row {1}").format(d.fieldtype, d.idx)
			)

	def check_dynamic_link_options(d):
		if d.fieldtype == "Dynamic Link":
			doctype_pointer = list(filter(lambda df: df.fieldname == d.options, fields))
			if (
				not doctype_pointer
				or (doctype_pointer[0].fieldtype not in ("Link", "Select"))
				or (doctype_pointer[0].fieldtype == "Link" and doctype_pointer[0].options != "DocType")
			):
				frappe.throw(
					_(
						"Options 'Dynamic Link' type of field must point to another Link Field with options as 'DocType'"
					)
				)

	def check_illegal_default(d):
		if d.fieldtype == "Check" and not d.default:
			d.default = "0"
		if d.fieldtype == "Check" and cint(d.default) not in (0, 1):
			frappe.throw(
				_("Default for 'Check' type of field {0} must be either '0' or '1'").format(
					frappe.bold(d.fieldname)
				)
			)
		if d.fieldtype == "Select" and d.default:
			if not d.options:
				frappe.throw(
					_("Options for {0} must be set before setting the default value.").format(
						frappe.bold(d.fieldname)
					)
				)
			elif d.default not in d.options.split("\n"):
				frappe.throw(
					_("Default value for {0} must be in the list of options.").format(frappe.bold(d.fieldname))
				)

	def check_precision(d):
		if (
			d.fieldtype in ("Currency", "Float", "Percent")
			and d.precision is not None
			and not (1 <= cint(d.precision) <= 6)
		):
			frappe.throw(_("Precision should be between 1 and 6"))

	def check_unique_and_text(docname, d):
		if meta.is_virtual:
			return

		if meta.issingle:
			d.unique = 0
			d.search_index = 0

		if getattr(d, "unique", False):
			if d.fieldtype not in ("Data", "Link", "Read Only"):
				frappe.throw(
					_("{0}: Fieldtype {1} for {2} cannot be unique").format(docname, d.fieldtype, d.label),
					NonUniqueError,
				)

			if not d.get("__islocal") and frappe.db.has_column(d.parent, d.fieldname):
				has_non_unique_values = frappe.db.sql(
					"""select `{fieldname}`, count(*)
					from `tab{doctype}` where ifnull(`{fieldname}`, '') != ''
					group by `{fieldname}` having count(*) > 1 limit 1""".format(
						doctype=d.parent, fieldname=d.fieldname
					)
				)

				if has_non_unique_values and has_non_unique_values[0][0]:
					frappe.throw(
						_("{0}: Field '{1}' cannot be set as Unique as it has non-unique values").format(
							docname, d.label
						),
						NonUniqueError,
					)

		if d.search_index and d.fieldtype in ("Text", "Long Text", "Small Text", "Code", "Text Editor"):
			frappe.throw(
				_("{0}:Fieldtype {1} for {2} cannot be indexed").format(docname, d.fieldtype, d.label),
				CannotIndexedError,
			)

	def check_fold(fields):
		fold_exists = False
		for i, f in enumerate(fields):
			if f.fieldtype == "Fold":
				if fold_exists:
					frappe.throw(_("There can be only one Fold in a form"))
				fold_exists = True
				if i < len(fields) - 1:
					nxt = fields[i + 1]
					if nxt.fieldtype != "Section Break":
						frappe.throw(_("Fold must come before a Section Break"))
				else:
					frappe.throw(_("Fold can not be at the end of the form"))

	def check_search_fields(meta, fields):
		"""Throw exception if `search_fields` don't contain valid fields."""
		if not meta.search_fields:
			return

		# No value fields should not be included in search field
		search_fields = [field.strip() for field in (meta.search_fields or "").split(",")]
		fieldtype_mapper = {
			field.fieldname: field.fieldtype
			for field in filter(lambda field: field.fieldname in search_fields, fields)
		}

		for fieldname in search_fields:
			fieldname = fieldname.strip()
			if (fieldtype_mapper.get(fieldname) in no_value_fields) or (fieldname not in fieldname_list):
				frappe.throw(_("Search field {0} is not valid").format(fieldname))

	def check_title_field(meta):
		"""Throw exception if `title_field` isn't a valid fieldname."""
		if not meta.get("title_field"):
			return

		if meta.title_field not in fieldname_list:
			frappe.throw(_("Title field must be a valid fieldname"), InvalidFieldNameError)

		def _validate_title_field_pattern(pattern):
			if not pattern:
				return

			for fieldname in FIELD_PATTERN.findall(pattern):
				if fieldname.startswith("{"):
					# edge case when double curlies are used for escape
					continue

				if fieldname not in fieldname_list:
					frappe.throw(
						_("{{{0}}} is not a valid fieldname pattern. It should be {{field_name}}.").format(
							fieldname
						),
						InvalidFieldNameError,
					)

		df = meta.get("fields", filters={"fieldname": meta.title_field})[0]
		if df:
			_validate_title_field_pattern(df.options)
			_validate_title_field_pattern(df.default)

	def check_image_field(meta):
		'''check image_field exists and is of type "Attach Image"'''
		if not meta.image_field:
			return

		df = meta.get("fields", {"fieldname": meta.image_field})
		if not df:
			frappe.throw(_("Image field must be a valid fieldname"), InvalidFieldNameError)
		if df[0].fieldtype != "Attach Image":
			frappe.throw(_("Image field must be of type Attach Image"), InvalidFieldNameError)

	def check_is_published_field(meta):
		if not meta.is_published_field:
			return

		if meta.is_published_field not in fieldname_list:
			frappe.throw(_("Is Published Field must be a valid fieldname"), InvalidFieldNameError)

	def check_website_search_field(meta):
		if not meta.get("website_search_field"):
			return

		if meta.website_search_field not in fieldname_list:
			frappe.throw(_("Website Search Field must be a valid fieldname"), InvalidFieldNameError)

		if "title" not in fieldname_list:
			frappe.throw(
				_('Field "title" is mandatory if "Website Search Field" is set.'), title=_("Missing Field")
			)

	def check_timeline_field(meta):
		if not meta.timeline_field:
			return

		if meta.timeline_field not in fieldname_list:
			frappe.throw(_("Timeline field must be a valid fieldname"), InvalidFieldNameError)

		df = meta.get("fields", {"fieldname": meta.timeline_field})[0]
		if df.fieldtype not in ("Link", "Dynamic Link"):
			frappe.throw(_("Timeline field must be a Link or Dynamic Link"), InvalidFieldNameError)

	def check_sort_field(meta):
		"""Validate that sort_field(s) is a valid field"""
		if meta.sort_field:
			sort_fields = [meta.sort_field]
			if "," in meta.sort_field:
				sort_fields = [d.split(maxsplit=1)[0] for d in meta.sort_field.split(",")]

			for fieldname in sort_fields:
				if fieldname not in (fieldname_list + list(default_fields) + list(child_table_fields)):
					frappe.throw(
						_("Sort field {0} must be a valid fieldname").format(fieldname), InvalidFieldNameError
					)

	def check_illegal_depends_on_conditions(docfield):
		"""assignment operation should not be allowed in the depends on condition."""
		depends_on_fields = [
			"depends_on",
			"collapsible_depends_on",
			"mandatory_depends_on",
			"read_only_depends_on",
		]
		for field in depends_on_fields:
			depends_on = docfield.get(field, None)
			if depends_on and ("=" in depends_on) and DEPENDS_ON_PATTERN.match(depends_on):
				frappe.throw(_("Invalid {0} condition").format(frappe.unscrub(field)), frappe.ValidationError)

	def check_table_multiselect_option(docfield):
		"""check if the doctype provided in Option has atleast 1 Link field"""
		if not docfield.fieldtype == "Table MultiSelect":
			return

		doctype = docfield.options
		meta = frappe.get_meta(doctype)
		link_field = [df for df in meta.fields if df.fieldtype == "Link"]

		if not link_field:
			frappe.throw(
				_(
					"DocType <b>{0}</b> provided for the field <b>{1}</b> must have atleast one Link field"
				).format(doctype, docfield.fieldname),
				frappe.ValidationError,
			)

	def scrub_options_in_select(field):
		"""Strip options for whitespaces"""

		if field.fieldtype == "Select" and field.options is not None:
			options_list = []
			for i, option in enumerate(field.options.split("\n")):
				_option = option.strip()
				if i == 0 or _option:
					options_list.append(_option)
			field.options = "\n".join(options_list)

	def scrub_fetch_from(field):
		if hasattr(field, "fetch_from") and getattr(field, "fetch_from"):
			field.fetch_from = field.fetch_from.strip("\n").strip()

	def validate_data_field_type(docfield):
		if docfield.get("is_virtual"):
			return

		if docfield.fieldtype == "Data" and not (
			docfield.oldfieldtype and docfield.oldfieldtype != "Data"
		):
			if docfield.options and (docfield.options not in data_field_options):
				df_str = frappe.bold(_(docfield.label))
				text_str = (
					_("{0} is an invalid Data field.").format(df_str)
					+ "<br>" * 2
					+ _("Only Options allowed for Data field are:")
					+ "<br>"
				)
				df_options_str = "<ul><li>" + "</li><li>".join(_(x) for x in data_field_options) + "</ul>"

				frappe.msgprint(text_str + df_options_str, title="Invalid Data Field", alert=True)

	def check_child_table_option(docfield):
		if frappe.flags.in_fixtures:
			return
		if docfield.fieldtype not in ["Table MultiSelect", "Table"]:
			return

		doctype = docfield.options
		meta = frappe.get_meta(doctype)

		if not meta.istable:
			frappe.throw(
				_("Option {0} for field {1} is not a child table").format(
					frappe.bold(doctype), frappe.bold(docfield.fieldname)
				),
				title=_("Invalid Option"),
			)

	def check_max_height(docfield):
		if getattr(docfield, "max_height", None) and (docfield.max_height[-2:] not in ("px", "em")):
			frappe.throw(f"Max for {frappe.bold(docfield.fieldname)} height must be in px, em, rem")

	def check_no_of_ratings(docfield):
		if docfield.fieldtype == "Rating":
			if docfield.options and (int(docfield.options) > 10 or int(docfield.options) < 3):
				frappe.throw(_("Options for Rating field can range from 3 to 10"))

	fields = meta.get("fields")
	fieldname_list = [d.fieldname for d in fields]

	not_allowed_in_list_view = get_fields_not_allowed_in_list_view(meta)

	for d in fields:
		if not d.permlevel:
			d.permlevel = 0
		if d.fieldtype not in table_fields:
			d.allow_bulk_edit = 0
		if not d.fieldname:
			d.fieldname = d.fieldname.lower().strip("?")

		check_illegal_characters(d.fieldname)
		check_invalid_fieldnames(meta.get("name"), d.fieldname)
		check_unique_fieldname(meta.get("name"), d.fieldname)
		check_fieldname_length(d.fieldname)
		check_hidden_and_mandatory(meta.get("name"), d)
		check_unique_and_text(meta.get("name"), d)
		check_table_multiselect_option(d)
		scrub_options_in_select(d)
		scrub_fetch_from(d)
		validate_data_field_type(d)

		if not frappe.flags.in_migrate:
			check_link_table_options(meta.get("name"), d)
			check_illegal_mandatory(meta.get("name"), d)
			check_dynamic_link_options(d)
			check_in_list_view(meta.get("istable"), d)
			check_in_global_search(d)
			check_illegal_depends_on_conditions(d)
			check_illegal_default(d)
			check_child_table_option(d)
			check_max_height(d)
			check_no_of_ratings(d)

	if not frappe.flags.in_migrate:
		check_fold(fields)
		check_search_fields(meta, fields)
		check_title_field(meta)
		check_timeline_field(meta)
		check_is_published_field(meta)
		check_website_search_field(meta)
		check_sort_field(meta)
		check_image_field(meta)


def get_fields_not_allowed_in_list_view(meta) -> list[str]:
	not_allowed_in_list_view = list(copy.copy(no_value_fields))
	not_allowed_in_list_view.append("Attach Image")
	if meta.istable:
		not_allowed_in_list_view.remove("Button")
		not_allowed_in_list_view.remove("HTML")
	return not_allowed_in_list_view


def validate_permissions_for_doctype(doctype, for_remove=False, alert=False):
	"""Validates if permissions are set correctly."""
	doctype = frappe.get_doc("DocType", doctype)
	validate_permissions(doctype, for_remove, alert=alert)

	# save permissions
	for perm in doctype.get("permissions"):
		perm.db_update()

	clear_permissions_cache(doctype.name)


def clear_permissions_cache(doctype):
	frappe.clear_cache(doctype=doctype)
	delete_notification_count_for(doctype)
	for user in frappe.db.sql_list(
		"""
		SELECT
			DISTINCT `tabHas Role`.`parent`
		FROM
			`tabHas Role`,
			`tabDocPerm`
		WHERE `tabDocPerm`.`parent` = %s
			AND `tabDocPerm`.`role` = `tabHas Role`.`role`
			AND `tabHas Role`.`parenttype` = 'User'
		""",
		doctype,
	):
		frappe.clear_cache(user=user)


def validate_permissions(doctype, for_remove=False, alert=False):
	permissions = doctype.get("permissions")
	# Some DocTypes may not have permissions by default, don't show alert for them
	if not permissions and alert:
		frappe.msgprint(_("No Permissions Specified"), alert=True, indicator="orange")
	issingle = issubmittable = isimportable = False
	if doctype:
		issingle = cint(doctype.issingle)
		issubmittable = cint(doctype.is_submittable)
		isimportable = cint(doctype.allow_import)

	def get_txt(d):
		return _("For {0} at level {1} in {2} in row {3}").format(d.role, d.permlevel, d.parent, d.idx)

	def check_atleast_one_set(d):
		if (
			not d.select and not d.read and not d.write and not d.submit and not d.cancel and not d.create
		):
			frappe.throw(_("{0}: No basic permissions set").format(get_txt(d)))

	def check_double(d):
		has_similar = False
		similar_because_of = ""
		for p in permissions:
			if p.role == d.role and p.permlevel == d.permlevel and p != d:
				if p.if_owner == d.if_owner:
					similar_because_of = _("If Owner")
					has_similar = True
					break

		if has_similar:
			frappe.throw(
				_("{0}: Only one rule allowed with the same Role, Level and {1}").format(
					get_txt(d), similar_because_of
				)
			)

	def check_level_zero_is_set(d):
		if cint(d.permlevel) > 0 and d.role != "All":
			has_zero_perm = False
			for p in permissions:
				if p.role == d.role and (p.permlevel or 0) == 0 and p != d:
					has_zero_perm = True
					break

			if not has_zero_perm:
				frappe.throw(
					_("{0}: Permission at level 0 must be set before higher levels are set").format(get_txt(d))
				)

			for invalid in ("create", "submit", "cancel", "amend"):
				if d.get(invalid):
					d.set(invalid, 0)

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

		for ptype, label in [["set_user_permissions", _("Set User Permissions")]]:
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

	def validate_permission_for_all_role(d):
		if frappe.session.user == "Administrator":
			return

		if doctype.custom:
			if d.role == "All":
				frappe.throw(
					_("Row # {0}: Non administrator user can not set the role {1} to the custom doctype").format(
						d.idx, frappe.bold(_("All"))
					),
					title=_("Permissions Error"),
				)

			roles = [row.name for row in frappe.get_all("Role", filters={"is_custom": 1})]

			if d.role in roles:
				frappe.throw(
					_("Row # {0}: Non administrator user can not set the role {1} to the custom doctype").format(
						d.idx, frappe.bold(_(d.role))
					),
					title=_("Permissions Error"),
				)

	for d in permissions:
		if not d.permlevel:
			d.permlevel = 0
		check_atleast_one_set(d)
		if not for_remove:
			check_double(d)
			check_permission_dependency(d)
			check_if_submittable(d)
			check_if_importable(d)
		check_level_zero_is_set(d)
		remove_rights_for_single(d)
		validate_permission_for_all_role(d)


def make_module_and_roles(doc, perm_fieldname="permissions"):
	"""Make `Module Def` and `Role` records if already not made. Called while installing."""
	try:
		if (
			hasattr(doc, "restrict_to_domain")
			and doc.restrict_to_domain
			and not frappe.db.exists("Domain", doc.restrict_to_domain)
		):
			frappe.get_doc(dict(doctype="Domain", domain=doc.restrict_to_domain)).insert()

		if "tabModule Def" in frappe.db.get_tables() and not frappe.db.exists("Module Def", doc.module):
			m = frappe.get_doc({"doctype": "Module Def", "module_name": doc.module})
			if frappe.scrub(doc.module) in frappe.local.module_app:
				m.app_name = frappe.local.module_app[frappe.scrub(doc.module)]
			else:
				m.app_name = "frappe"
			m.flags.ignore_mandatory = m.flags.ignore_permissions = True
			if frappe.flags.package:
				m.package = frappe.flags.package.name
				m.custom = 1
			m.insert()

		default_roles = ["Administrator", "Guest", "All"]
		roles = [p.role for p in doc.get("permissions") or []] + default_roles

		for role in list(set(roles)):
			if frappe.db.table_exists("Role", cached=False) and not frappe.db.exists("Role", role):
				r = frappe.new_doc("Role")
				r.role_name = role
				r.desk_access = 1
				r.flags.ignore_mandatory = r.flags.ignore_permissions = True
				r.insert()
	except frappe.DoesNotExistError as e:
		pass
	except frappe.db.ProgrammingError as e:
		if frappe.db.is_table_missing(e):
			pass
		else:
			raise


def is_a_property(x) -> bool:
	"""Get properties (@property, @cached_property) in a controller class"""
	from functools import cached_property

	return isinstance(x, (property, cached_property))


def check_fieldname_conflicts(docfield):
	"""Checks if fieldname conflicts with methods or properties"""
	doc = frappe.get_doc({"doctype": docfield.dt})
	available_objects = [x for x in dir(doc) if isinstance(x, str)]
	property_list = [x for x in available_objects if is_a_property(getattr(type(doc), x, None))]
	method_list = [
		x for x in available_objects if x not in property_list and callable(getattr(doc, x))
	]
	msg = _("Fieldname {0} conflicting with meta object").format(docfield.fieldname)

	if docfield.fieldname in method_list + property_list:
		frappe.msgprint(msg, raise_exception=not docfield.is_virtual)


def clear_linked_doctype_cache():
	frappe.cache().delete_value("linked_doctypes_without_ignore_user_permissions_enabled")


def check_email_append_to(doc):
	if not hasattr(doc, "email_append_to") or not doc.email_append_to:
		return

	# Subject Field
	doc.subject_field = doc.subject_field.strip() if doc.subject_field else None
	subject_field = get_field(doc, doc.subject_field)

	if doc.subject_field and not subject_field:
		frappe.throw(_("Select a valid Subject field for creating documents from Email"))

	if subject_field and subject_field.fieldtype not in [
		"Data",
		"Text",
		"Long Text",
		"Small Text",
		"Text Editor",
	]:
		frappe.throw(_("Subject Field type should be Data, Text, Long Text, Small Text, Text Editor"))

	# Sender Field is mandatory
	doc.sender_field = doc.sender_field.strip() if doc.sender_field else None
	sender_field = get_field(doc, doc.sender_field)

	if doc.sender_field and not sender_field:
		frappe.throw(_("Select a valid Sender Field for creating documents from Email"))

	if not sender_field.options == "Email":
		frappe.throw(_("Sender Field should have Email in options"))


def get_field(doc, fieldname):
	if not (doc or fieldname):
		return

	for field in doc.fields:
		if field.fieldname == fieldname:
			return field
