# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals, print_function
import frappe
import time
from frappe import _, msgprint
from frappe.utils import flt, cstr, now, get_datetime_str, file_lock, date_diff
from frappe.utils.background_jobs import enqueue
from frappe.model.base_document import BaseDocument, get_controller
from frappe.model.naming import set_new_name
from six import iteritems, string_types
from werkzeug.exceptions import NotFound, Forbidden
import hashlib, json
from frappe.model import optional_fields, table_fields
from frappe.model.workflow import validate_workflow
from frappe.model.workflow import set_workflow_state_on_action
from frappe.utils.global_search import update_global_search
from frappe.integrations.doctype.webhook import run_webhooks
from frappe.desk.form.document_follow import follow_document
from frappe.core.doctype.server_script.server_script_utils import run_server_script_for_doc_event

# once_only validation
# methods

def get_doc(*args, **kwargs):
	"""returns a frappe.model.Document object.

	:param arg1: Document dict or DocType name.
	:param arg2: [optional] document name.

	There are multiple ways to call `get_doc`

		# will fetch the latest user object (with child table) from the database
		user = get_doc("User", "test@example.com")

		# create a new object
		user = get_doc({
			"doctype":"User"
			"email_id": "test@example.com",
			"roles: [
				{"role": "System Manager"}
			]
		})

		# create new object with keyword arguments
		user = get_doc(doctype='User', email_id='test@example.com')
	"""
	if args:
		if isinstance(args[0], BaseDocument):
			# already a document
			return args[0]
		elif isinstance(args[0], string_types):
			doctype = args[0]

		elif isinstance(args[0], dict):
			# passed a dict
			kwargs = args[0]

		else:
			raise ValueError('First non keyword argument must be a string or dict')

	if kwargs:
		if 'doctype' in kwargs:
			doctype = kwargs['doctype']
		else:
			raise ValueError('"doctype" is a required key')

	controller = get_controller(doctype)
	if controller:
		return controller(*args, **kwargs)

	raise ImportError(doctype)

class Document(BaseDocument):
	"""All controllers inherit from `Document`."""
	def __init__(self, *args, **kwargs):
		"""Constructor.

		:param arg1: DocType name as string or document **dict**
		:param arg2: Document name, if `arg1` is DocType name.

		If DocType name and document name are passed, the object will load
		all values (including child documents) from the database.
		"""
		self.doctype = self.name = None
		self._default_new_docs = {}
		self.flags = frappe._dict()

		if args and args[0] and isinstance(args[0], string_types):
			# first arugment is doctype
			if len(args)==1:
				# single
				self.doctype = self.name = args[0]
			else:
				self.doctype = args[0]
				if isinstance(args[1], dict):
					# filter
					self.name = frappe.db.get_value(args[0], args[1], "name")
					if self.name is None:
						frappe.throw(_("{0} {1} not found").format(_(args[0]), args[1]),
							frappe.DoesNotExistError)
				else:
					self.name = args[1]

			self.load_from_db()
			return

		if args and args[0] and isinstance(args[0], dict):
			# first argument is a dict
			kwargs = args[0]

		if kwargs:
			# init base document
			super(Document, self).__init__(kwargs)
			self.init_valid_columns()

		else:
			# incorrect arguments. let's not proceed.
			raise ValueError('Illegal arguments')

	@staticmethod
	def whitelist(f):
		"""Decorator: Whitelist method to be called remotely via REST API."""
		f.whitelisted = True
		return f

	def reload(self):
		"""Reload document from database"""
		self.load_from_db()

	def load_from_db(self):
		"""Load document and children from database and create properties
		from fields"""
		if not getattr(self, "_metaclass", False) and self.meta.issingle:
			single_doc = frappe.db.get_singles_dict(self.doctype)
			if not single_doc:
				single_doc = frappe.new_doc(self.doctype).as_dict()
				single_doc["name"] = self.doctype
				del single_doc["__islocal"]

			super(Document, self).__init__(single_doc)
			self.init_valid_columns()
			self._fix_numeric_types()

		else:
			d = frappe.db.get_value(self.doctype, self.name, "*", as_dict=1)
			if not d:
				frappe.throw(_("{0} {1} not found").format(_(self.doctype), self.name), frappe.DoesNotExistError)

			super(Document, self).__init__(d)

		if self.name=="DocType" and self.doctype=="DocType":
			from frappe.model.meta import DOCTYPE_TABLE_FIELDS
			table_fields = DOCTYPE_TABLE_FIELDS
		else:
			table_fields = self.meta.get_table_fields()

		for df in table_fields:
			children = frappe.db.get_values(df.options,
				{"parent": self.name, "parenttype": self.doctype, "parentfield": df.fieldname},
				"*", as_dict=True, order_by="idx asc")
			if children:
				self.set(df.fieldname, children)
			else:
				self.set(df.fieldname, [])

		# sometimes __setup__ can depend on child values, hence calling again at the end
		if hasattr(self, "__setup__"):
			self.__setup__()

	def get_latest(self):
		if not getattr(self, "latest", None):
			self.latest = frappe.get_doc(self.doctype, self.name)
		return self.latest

	def check_permission(self, permtype='read', permlevel=None):
		"""Raise `frappe.PermissionError` if not permitted"""
		if not self.has_permission(permtype):
			self.raise_no_permission_to(permlevel or permtype)

	def has_permission(self, permtype="read", verbose=False):
		"""Call `frappe.has_permission` if `self.flags.ignore_permissions`
		is not set.

		:param permtype: one of `read`, `write`, `submit`, `cancel`, `delete`"""
		if self.flags.ignore_permissions:
			return True
		return frappe.has_permission(self.doctype, permtype, self, verbose=verbose)

	def raise_no_permission_to(self, perm_type):
		"""Raise `frappe.PermissionError`."""
		frappe.flags.error_message = _('Insufficient Permission for {0}').format(self.doctype)
		raise frappe.PermissionError

	def insert(self, ignore_permissions=None, ignore_links=None, ignore_if_duplicate=False,
				ignore_mandatory=None, set_name=None, set_child_names=True):
		"""Insert the document in the database (as a new document).
		This will check for user permissions and execute `before_insert`,
		`validate`, `on_update`, `after_insert` methods if they are written.

		:param ignore_permissions: Do not check permissions if True."""
		if self.flags.in_print:
			return

		self.flags.notifications_executed = []

		if ignore_permissions!=None:
			self.flags.ignore_permissions = ignore_permissions

		if ignore_links!=None:
			self.flags.ignore_links = ignore_links

		if ignore_mandatory!=None:
			self.flags.ignore_mandatory = ignore_mandatory

		self.set("__islocal", True)

		self.check_permission("create")
		self._set_defaults()
		self.set_user_and_timestamp()
		self.set_docstatus()
		self.check_if_latest()
		self.run_method("before_insert")
		self._validate_links()
		self.set_new_name(set_name=set_name, set_child_names=set_child_names)
		self.set_parent_in_children()
		self.validate_higher_perm_levels()

		self.flags.in_insert = True
		self.run_before_save_methods()
		self._validate()
		self.set_docstatus()
		self.flags.in_insert = False

		# follow document on document creation


		# run validate, on update etc.

		# parent
		if getattr(self.meta, "issingle", 0):
			self.update_single(self.get_valid_dict())
		else:
			try:
				self.db_insert()
			except frappe.DuplicateEntryError as e:
				if not ignore_if_duplicate:
					raise e

		# children
		for d in self.get_all_children():
			d.db_insert()

		self.run_method("after_insert")
		self.flags.in_insert = True

		if self.get("amended_from"):
			self.copy_attachments_from_amended_from()

		# flag to prevent creation of event update log for create and update both
		# during document creation
		self.flags.update_log_for_doc_creation = True
		self.run_post_save_methods()
		self.flags.in_insert = False

		# delete __islocal
		if hasattr(self, "__islocal"):
			delattr(self, "__islocal")

		# clear unsaved flag
		if hasattr(self, "__unsaved"):
			delattr(self, "__unsaved")

		if not (frappe.flags.in_migrate or frappe.local.flags.in_install or frappe.flags.in_setup_wizard):
			follow_document(self.doctype, self.name, frappe.session.user)
		return self

	def save(self, *args, **kwargs):
		"""Wrapper for _save"""
		return self._save(*args, **kwargs)

	def _save(self, ignore_permissions=None, ignore_version=None):
		"""Save the current document in the database in the **DocType**'s table or
		`tabSingles` (for single types).

		This will check for user permissions and execute
		`validate` before updating, `on_update` after updating triggers.

		:param ignore_permissions: Do not check permissions if True.
		:param ignore_version: Do not save version if True."""
		if self.flags.in_print:
			return

		self.flags.notifications_executed = []

		if ignore_permissions!=None:
			self.flags.ignore_permissions = ignore_permissions

		self.flags.ignore_version = frappe.flags.in_test if ignore_version is None else ignore_version

		if self.get("__islocal") or not self.get("name"):
			self.insert()
			return

		self.check_permission("write", "save")

		self.set_user_and_timestamp()
		self.set_docstatus()
		self.check_if_latest()
		self.set_parent_in_children()
		self.set_name_in_children()

		self.validate_higher_perm_levels()
		self._validate_links()
		self.run_before_save_methods()

		if self._action != "cancel":
			self._validate()

		if self._action == "update_after_submit":
			self.validate_update_after_submit()

		self.set_docstatus()

		# parent
		if self.meta.issingle:
			self.update_single(self.get_valid_dict())
		else:
			self.db_update()

		self.update_children()
		self.run_post_save_methods()

		# clear unsaved flag
		if hasattr(self, "__unsaved"):
			delattr(self, "__unsaved")

		return self

	def copy_attachments_from_amended_from(self):
		"""Copy attachments from `amended_from`"""
		from frappe.desk.form.load import get_attachments

		#loop through attachments
		for attach_item in get_attachments(self.doctype, self.amended_from):

			#save attachments to new doc
			_file = frappe.get_doc({
				"doctype": "File",
				"file_url": attach_item.file_url,
				"file_name": attach_item.file_name,
				"attached_to_name": self.name,
				"attached_to_doctype": self.doctype,
				"folder": "Home/Attachments"})
			_file.save()


	def update_children(self):
		"""update child tables"""
		for df in self.meta.get_table_fields():
			self.update_child_table(df.fieldname, df)

	def update_child_table(self, fieldname, df=None):
		"""sync child table for given fieldname"""
		rows = []
		if not df:
			df = self.meta.get_field(fieldname)

		for d in self.get(df.fieldname):
			d.db_update()
			rows.append(d.name)

		if df.options in (self.flags.ignore_children_type or []):
			# do not delete rows for this because of flags
			# hack for docperm :(
			return

		if rows:
			# select rows that do not match the ones in the document
			deleted_rows = frappe.db.sql("""select name from `tab{0}` where parent=%s
				and parenttype=%s and parentfield=%s
				and name not in ({1})""".format(df.options, ','.join(['%s'] * len(rows))),
					[self.name, self.doctype, fieldname] + rows)
			if len(deleted_rows) > 0:
				# delete rows that do not match the ones in the document
				frappe.db.sql("""delete from `tab{0}` where name in ({1})""".format(df.options,
					','.join(['%s'] * len(deleted_rows))), tuple(row[0] for row in deleted_rows))

		else:
			# no rows found, delete all rows
			frappe.db.sql("""delete from `tab{0}` where parent=%s
				and parenttype=%s and parentfield=%s""".format(df.options),
				(self.name, self.doctype, fieldname))

	def get_doc_before_save(self):
		return getattr(self, '_doc_before_save', None)

	def has_value_changed(self, fieldname):
		'''Returns true if value is changed before and after saving'''
		previous = self.get_doc_before_save()
		return previous.get(fieldname)!=self.get(fieldname) if previous else True

	def set_new_name(self, force=False, set_name=None, set_child_names=True):
		"""Calls `frappe.naming.set_new_name` for parent and child docs."""
		if self.flags.name_set and not force:
			return

		if set_name:
			self.name = set_name
		else:
			set_new_name(self)

		if set_child_names:
			# set name for children
			for d in self.get_all_children():
				set_new_name(d)

		self.flags.name_set = True

	def get_title(self):
		"""Get the document title based on title_field or `title` or `name`"""
		return self.get(self.meta.get_title_field())

	def set_title_field(self):
		"""Set title field based on template"""
		def get_values():
			values = self.as_dict()
			# format values
			for key, value in iteritems(values):
				if value==None:
					values[key] = ""
			return values

		if self.meta.get("title_field")=="title":
			df = self.meta.get_field(self.meta.title_field)

			if df.options:
				self.set(df.fieldname, df.options.format(**get_values()))
			elif self.is_new() and not self.get(df.fieldname) and df.default:
				# set default title for new transactions (if default)
				self.set(df.fieldname, df.default.format(**get_values()))

	def update_single(self, d):
		"""Updates values for Single type Document in `tabSingles`."""
		frappe.db.sql("""delete from `tabSingles` where doctype=%s""", self.doctype)
		for field, value in iteritems(d):
			if field != "doctype":
				frappe.db.sql("""insert into `tabSingles` (doctype, field, value)
					values (%s, %s, %s)""", (self.doctype, field, value))

		if self.doctype in frappe.db.value_cache:
			del frappe.db.value_cache[self.doctype]

	def set_user_and_timestamp(self):
		self._original_modified = self.modified
		self.modified = now()
		self.modified_by = frappe.session.user
		if not self.creation:
			self.creation = self.modified
		if not self.owner:
			self.owner = self.modified_by

		for d in self.get_all_children():
			d.modified = self.modified
			d.modified_by = self.modified_by
			if not d.owner:
				d.owner = self.owner
			if not d.creation:
				d.creation = self.creation

		frappe.flags.currently_saving.append((self.doctype, self.name))

	def set_docstatus(self):
		if self.docstatus==None:
			self.docstatus=0

		for d in self.get_all_children():
			d.docstatus = self.docstatus

	def _validate(self):
		self._validate_mandatory()
		self._validate_data_fields()
		self._validate_selects()
		self._validate_length()
		self._extract_images_from_text_editor()
		self._sanitize_content()
		self._save_passwords()
		self.validate_workflow()

		children = self.get_all_children()
		for d in children:
			d._validate_data_fields()
			d._validate_selects()
			d._validate_length()
			d._extract_images_from_text_editor()
			d._sanitize_content()
			d._save_passwords()
		if self.is_new():
			# don't set fields like _assign, _comments for new doc
			for fieldname in optional_fields:
				self.set(fieldname, None)
		else:
			self.validate_set_only_once()

	def validate_workflow(self):
		"""Validate if the workflow transition is valid"""
		if frappe.flags.in_install == 'frappe': return
		workflow = self.meta.get_workflow()
		if workflow:
			validate_workflow(self)
			if not self._action == 'save':
				set_workflow_state_on_action(self, workflow, self._action)

	def validate_set_only_once(self):
		"""Validate that fields are not changed if not in insert"""
		set_only_once_fields = self.meta.get_set_only_once_fields()

		if set_only_once_fields and self._doc_before_save:
			# document exists before saving
			for field in set_only_once_fields:
				fail = False
				value = self.get(field.fieldname)
				original_value = self._doc_before_save.get(field.fieldname)

				if field.fieldtype in table_fields:
					fail = not self.is_child_table_same(field.fieldname)
				elif field.fieldtype in ('Date', 'Datetime', 'Time'):
					fail = str(value) != str(original_value)
				else:
					fail = value != original_value

				if fail:
					frappe.throw(_("Value cannot be changed for {0}").format(self.meta.get_label(field.fieldname)),
						frappe.CannotChangeConstantError)

		return False

	def is_child_table_same(self, fieldname):
		"""Validate child table is same as original table before saving"""
		value = self.get(fieldname)
		original_value = self._doc_before_save.get(fieldname)
		same = True

		if len(original_value) != len(value):
			same = False
		else:
			# check all child entries
			for i, d in enumerate(original_value):
				new_child = value[i].as_dict(convert_dates_to_str = True)
				original_child = d.as_dict(convert_dates_to_str = True)

				# all fields must be same other than modified and modified_by
				for key in ('modified', 'modified_by', 'creation'):
					del new_child[key]
					del original_child[key]

				if original_child != new_child:
					same = False
					break

		return same

	def apply_fieldlevel_read_permissions(self):
		"""Remove values the user is not allowed to read (called when loading in desk)"""
		has_higher_permlevel = False
		for p in self.get_permissions():
			if p.permlevel > 0:
				has_higher_permlevel = True
				break

		if not has_higher_permlevel:
			return

		has_access_to = self.get_permlevel_access('read')

		for df in self.meta.fields:
			if df.permlevel and not df.permlevel in has_access_to:
				self.set(df.fieldname, None)

		for table_field in self.meta.get_table_fields():
			for df in frappe.get_meta(table_field.options).fields or []:
				if df.permlevel and not df.permlevel in has_access_to:
					for child in self.get(table_field.fieldname) or []:
						child.set(df.fieldname, None)

	def validate_higher_perm_levels(self):
		"""If the user does not have permissions at permlevel > 0, then reset the values to original / default"""
		if self.flags.ignore_permissions or frappe.flags.in_install:
			return

		has_access_to = self.get_permlevel_access()
		high_permlevel_fields = self.meta.get_high_permlevel_fields()

		if high_permlevel_fields:
			self.reset_values_if_no_permlevel_access(has_access_to, high_permlevel_fields)

		# If new record then don't reset the values for child table
		if self.is_new(): return

		# check for child tables
		for df in self.meta.get_table_fields():
			high_permlevel_fields = frappe.get_meta(df.options).get_high_permlevel_fields()
			if high_permlevel_fields:
				for d in self.get(df.fieldname):
					d.reset_values_if_no_permlevel_access(has_access_to, high_permlevel_fields)

	def get_permlevel_access(self, permission_type='write'):
		if not hasattr(self, "_has_access_to"):
			self._has_access_to = {}

		if not self._has_access_to.get(permission_type):
			self._has_access_to[permission_type] = []
			roles = frappe.get_roles()
			for perm in self.get_permissions():
				if perm.role in roles and perm.permlevel > 0 and perm.get(permission_type):
					if perm.permlevel not in self._has_access_to[permission_type]:
						self._has_access_to[permission_type].append(perm.permlevel)

		return self._has_access_to[permission_type]

	def has_permlevel_access_to(self, fieldname, df=None, permission_type='read'):
		if not df:
			df = self.meta.get_field(fieldname)

		return df.permlevel in self.get_permlevel_access(permission_type)

	def get_permissions(self):
		if self.meta.istable:
			# use parent permissions
			permissions = frappe.get_meta(self.parenttype).permissions
		else:
			permissions = self.meta.permissions

		return permissions

	def _set_defaults(self):
		if frappe.flags.in_import:
			return

		new_doc = frappe.new_doc(self.doctype, as_dict=True)
		self.update_if_missing(new_doc)

		# children
		for df in self.meta.get_table_fields():
			new_doc = frappe.new_doc(df.options, as_dict=True)
			value = self.get(df.fieldname)
			if isinstance(value, list):
				for d in value:
					d.update_if_missing(new_doc)

	def check_if_latest(self):
		"""Checks if `modified` timestamp provided by document being updated is same as the
		`modified` timestamp in the database. If there is a different, the document has been
		updated in the database after the current copy was read. Will throw an error if
		timestamps don't match.

		Will also validate document transitions (Save > Submit > Cancel) calling
		`self.check_docstatus_transition`."""
		conflict = False
		self._action = "save"
		if not self.get('__islocal'):
			if self.meta.issingle:
				modified = frappe.db.sql("""select value from tabSingles
					where doctype=%s and field='modified' for update""", self.doctype)
				modified = modified and modified[0][0]
				if modified and modified != cstr(self._original_modified):
					conflict = True
			else:
				tmp = frappe.db.sql("""select modified, docstatus from `tab{0}`
					where name = %s for update""".format(self.doctype), self.name, as_dict=True)

				if not tmp:
					frappe.throw(_("Record does not exist"))
				else:
					tmp = tmp[0]

				modified = cstr(tmp.modified)

				if modified and modified != cstr(self._original_modified):
					conflict = True

				self.check_docstatus_transition(tmp.docstatus)

			if conflict:
				frappe.msgprint(_("Error: Document has been modified after you have opened it") \
				+ (" (%s, %s). " % (modified, self.modified)) \
				+ _("Please refresh to get the latest document."),
					raise_exception=frappe.TimestampMismatchError)
		else:
			self.check_docstatus_transition(0)

	def check_docstatus_transition(self, docstatus):
		"""Ensures valid `docstatus` transition.
		Valid transitions are (number in brackets is `docstatus`):

		- Save (0) > Save (0)
		- Save (0) > Submit (1)
		- Submit (1) > Submit (1)
		- Submit (1) > Cancel (2)

		"""
		if not self.docstatus:
			self.docstatus = 0
		if docstatus==0:
			if self.docstatus==0:
				self._action = "save"
			elif self.docstatus==1:
				self._action = "submit"
				self.check_permission("submit")
			else:
				raise frappe.DocstatusTransitionError(_("Cannot change docstatus from 0 to 2"))

		elif docstatus==1:
			if self.docstatus==1:
				self._action = "update_after_submit"
				self.check_permission("submit")
			elif self.docstatus==2:
				self._action = "cancel"
				self.check_permission("cancel")
			else:
				raise frappe.DocstatusTransitionError(_("Cannot change docstatus from 1 to 0"))

		elif docstatus==2:
			raise frappe.ValidationError(_("Cannot edit cancelled document"))

	def set_parent_in_children(self):
		"""Updates `parent` and `parenttype` property in all children."""
		for d in self.get_all_children():
			d.parent = self.name
			d.parenttype = self.doctype

	def set_name_in_children(self):
		# Set name for any new children
		for d in self.get_all_children():
			if not d.name:
				set_new_name(d)

	def validate_update_after_submit(self):
		if self.flags.ignore_validate_update_after_submit:
			return

		self._validate_update_after_submit()
		for d in self.get_all_children():
			if d.is_new() and self.meta.get_field(d.parentfield).allow_on_submit:
				# in case of a new row, don't validate allow on submit, if table is allow on submit
				continue

			d._validate_update_after_submit()

		# TODO check only allowed values are updated

	def _validate_mandatory(self):
		if self.flags.ignore_mandatory:
			return

		missing = self._get_missing_mandatory_fields()
		for d in self.get_all_children():
			missing.extend(d._get_missing_mandatory_fields())

		if not missing:
			return

		for fieldname, msg in missing:
			msgprint(msg)

		if frappe.flags.print_messages:
			print(self.as_json().encode("utf-8"))

		raise frappe.MandatoryError('[{doctype}, {name}]: {fields}'.format(
			fields=", ".join((each[0] for each in missing)),
			doctype=self.doctype,
			name=self.name))

	def _validate_links(self):
		if self.flags.ignore_links or self._action == "cancel":
			return

		invalid_links, cancelled_links = self.get_invalid_links()

		for d in self.get_all_children():
			result = d.get_invalid_links(is_submittable=self.meta.is_submittable)
			invalid_links.extend(result[0])
			cancelled_links.extend(result[1])

		if invalid_links:
			msg = ", ".join((each[2] for each in invalid_links))
			frappe.throw(_("Could not find {0}").format(msg),
				frappe.LinkValidationError)

		if cancelled_links:
			msg = ", ".join((each[2] for each in cancelled_links))
			frappe.throw(_("Cannot link cancelled document: {0}").format(msg),
				frappe.CancelledLinkError)

	def get_all_children(self, parenttype=None):
		"""Returns all children documents from **Table** type field in a list."""
		ret = []
		for df in self.meta.get("fields", {"fieldtype": ['in', table_fields]}):
			if parenttype:
				if df.options==parenttype:
					return self.get(df.fieldname)
			value = self.get(df.fieldname)
			if isinstance(value, list):
				ret.extend(value)
		return ret

	def run_method(self, method, *args, **kwargs):
		"""run standard triggers, plus those in hooks"""
		if "flags" in kwargs:
			del kwargs["flags"]

		if hasattr(self, method) and hasattr(getattr(self, method), "__call__"):
			fn = lambda self, *args, **kwargs: getattr(self, method)(*args, **kwargs)
		else:
			# hack! to run hooks even if method does not exist
			fn = lambda self, *args, **kwargs: None

		fn.__name__ = str(method)
		out = Document.hook(fn)(self, *args, **kwargs)

		self.run_notifications(method)
		run_webhooks(self, method)
		run_server_script_for_doc_event(self, method)

		return out

	def run_trigger(self, method, *args, **kwargs):
		return self.run_method(method, *args, **kwargs)

	def run_notifications(self, method):
		"""Run notifications for this method"""
		if (frappe.flags.in_import and frappe.flags.mute_emails) or frappe.flags.in_patch or frappe.flags.in_install:
			return

		if self.flags.notifications_executed==None:
			self.flags.notifications_executed = []

		from frappe.email.doctype.notification.notification import evaluate_alert

		if self.flags.notifications == None:
			alerts = frappe.cache().hget('notifications', self.doctype)
			if alerts==None:
				alerts = frappe.get_all('Notification', fields=['name', 'event', 'method'],
					filters={'enabled': 1, 'document_type': self.doctype})
				frappe.cache().hset('notifications', self.doctype, alerts)
			self.flags.notifications = alerts

		if not self.flags.notifications:
			return

		def _evaluate_alert(alert):
			if not alert.name in self.flags.notifications_executed:
				evaluate_alert(self, alert.name, alert.event)
				self.flags.notifications_executed.append(alert.name)

		event_map = {
			"on_update": "Save",
			"after_insert": "New",
			"on_submit": "Submit",
			"on_cancel": "Cancel"
		}

		if not self.flags.in_insert:
			# value change is not applicable in insert
			event_map['on_change'] = 'Value Change'

		for alert in self.flags.notifications:
			event = event_map.get(method, None)
			if event and alert.event == event:
				_evaluate_alert(alert)
			elif alert.event=='Method' and method == alert.method:
				_evaluate_alert(alert)

	@whitelist.__func__
	def _submit(self):
		"""Submit the document. Sets `docstatus` = 1, then saves."""
		self.docstatus = 1
		self.save()

	@whitelist.__func__
	def _cancel(self):
		"""Cancel the document. Sets `docstatus` = 2, then saves."""
		self.docstatus = 2
		self.save()

	@whitelist.__func__
	def submit(self):
		"""Submit the document. Sets `docstatus` = 1, then saves."""
		self._submit()

	@whitelist.__func__
	def cancel(self):
		"""Cancel the document. Sets `docstatus` = 2, then saves."""
		self._cancel()

	def delete(self):
		"""Delete document."""
		frappe.delete_doc(self.doctype, self.name, flags=self.flags)

	def run_before_save_methods(self):
		"""Run standard methods before  `INSERT` or `UPDATE`. Standard Methods are:

		- `validate`, `before_save` for **Save**.
		- `validate`, `before_submit` for **Submit**.
		- `before_cancel` for **Cancel**
		- `before_update_after_submit` for **Update after Submit**

		Will also update title_field if set"""

		self.load_doc_before_save()
		self.reset_seen()

		if self.flags.ignore_validate:
			return

		if self._action=="save":
			self.run_method("before_validate")
			self.run_method("validate")
			self.run_method("before_save")
		elif self._action=="submit":
			self.run_method("before_validate")
			self.run_method("validate")
			self.run_method("before_submit")
		elif self._action=="cancel":
			self.run_method("before_cancel")
		elif self._action=="update_after_submit":
			self.run_method("before_update_after_submit")

		self.set_title_field()

	def load_doc_before_save(self):
		"""Save load document from db before saving"""
		self._doc_before_save = None
		if not self.is_new():
			try:
				self._doc_before_save = frappe.get_doc(self.doctype, self.name)
			except frappe.DoesNotExistError:
				self._doc_before_save = None
				frappe.clear_last_message()

	def run_post_save_methods(self):
		"""Run standard methods after `INSERT` or `UPDATE`. Standard Methods are:

		- `on_update` for **Save**.
		- `on_update`, `on_submit` for **Submit**.
		- `on_cancel` for **Cancel**
		- `update_after_submit` for **Update after Submit**"""

		doc_before_save = self.get_doc_before_save()

		if self._action=="save":
			self.run_method("on_update")
		elif self._action=="submit":
			self.run_method("on_update")
			self.run_method("on_submit")
		elif self._action=="cancel":
			self.run_method("on_cancel")
			self.check_no_back_links_exist()
		elif self._action=="update_after_submit":
			self.run_method("on_update_after_submit")


		self.clear_cache()
		self.notify_update()

		update_global_search(self)

		if getattr(self.meta, 'track_changes', False) and not self.flags.ignore_version \
			and not self.doctype == 'Version' and not frappe.flags.in_install:
			self.save_version()

		self.run_method('on_change')

		if (self.doctype, self.name) in frappe.flags.currently_saving:
			frappe.flags.currently_saving.remove((self.doctype, self.name))

		# make event update log for doctypes having event consumers
		if not frappe.flags.in_install and not frappe.flags.in_migrate and check_doctype_has_consumers(self.doctype):
			if self.flags.update_log_for_doc_creation:
				make_event_update_log(self, update_type='Create')
				self.flags.update_log_for_doc_creation = False
			else:
				from frappe.event_streaming.doctype.event_update_log.event_update_log import get_update
				diff = get_update(doc_before_save, self)
				if diff:
					doc = self
					doc.diff = diff
					make_event_update_log(doc, update_type='Update')

		self.latest = None

	def clear_cache(self):
		frappe.clear_document_cache(self.doctype, self.name)

	def reset_seen(self):
		"""Clear _seen property and set current user as seen"""
		if getattr(self.meta, 'track_seen', False):
			frappe.db.set_value(self.doctype, self.name, "_seen", json.dumps([frappe.session.user]), update_modified=False)

	def notify_update(self):
		"""Publish realtime that the current document is modified"""
		frappe.publish_realtime("doc_update", {"modified": self.modified, "doctype": self.doctype, "name": self.name},
			doctype=self.doctype, docname=self.name, after_commit=True)

		if not self.meta.get("read_only") and not self.meta.get("issingle") and \
			not self.meta.get("istable"):
			data = {
				"doctype": self.doctype,
				"name": self.name,
				"user": frappe.session.user
			}
			frappe.publish_realtime("list_update", data, after_commit=True)

	def db_set(self, fieldname, value=None, update_modified=True, notify=False, commit=False):
		"""Set a value in the document object, update the timestamp and update the database.

		WARNING: This method does not trigger controller validations and should
		be used very carefully.

		:param fieldname: fieldname of the property to be updated, or a {"field":"value"} dictionary
		:param value: value of the property to be updated
		:param update_modified: default True. updates the `modified` and `modified_by` properties
		:param notify: default False. run doc.notify_updated() to send updates via socketio
		:param commit: default False. run frappe.db.commit()
		"""
		if isinstance(fieldname, dict):
			self.update(fieldname)
		else:
			self.set(fieldname, value)

		if update_modified and (self.doctype, self.name) not in frappe.flags.currently_saving:
			# don't update modified timestamp if called from post save methods
			# like on_update or on_submit
			self.set("modified", now())
			self.set("modified_by", frappe.session.user)

		self.load_doc_before_save()
		# to trigger notification on value change
		self.run_method('before_change')

		frappe.db.set_value(self.doctype, self.name, fieldname, value,
			self.modified, self.modified_by, update_modified=update_modified)

		self.run_method('on_change')

		if notify:
			self.notify_update()

		self.clear_cache()
		if commit:
			frappe.db.commit()

	def db_get(self, fieldname):
		"""get database value for this fieldname"""
		return frappe.db.get_value(self.doctype, self.name, fieldname)

	def check_no_back_links_exist(self):
		"""Check if document links to any active document before Cancel."""
		from frappe.model.delete_doc import check_if_doc_is_linked, check_if_doc_is_dynamically_linked
		if not self.flags.ignore_links:
			check_if_doc_is_linked(self, method="Cancel")
			check_if_doc_is_dynamically_linked(self, method="Cancel")

	def save_version(self):
		"""Save version info"""
		if not self._doc_before_save and frappe.flags.in_patch: return

		version = frappe.new_doc('Version')
		if not self._doc_before_save:
			version.for_insert(self)
			version.insert(ignore_permissions=True)
		elif version.set_diff(self._doc_before_save, self):
			version.insert(ignore_permissions=True)
			if not frappe.flags.in_migrate:
				follow_document(self.doctype, self.name, frappe.session.user)

	@staticmethod
	def hook(f):
		"""Decorator: Make method `hookable` (i.e. extensible by another app).

		Note: If each hooked method returns a value (dict), then all returns are
		collated in one dict and returned. Ideally, don't return values in hookable
		methods, set properties in the document."""
		def add_to_return_value(self, new_return_value):
			if isinstance(new_return_value, dict):
				if not self.get("_return_value"):
					self._return_value = {}
				self._return_value.update(new_return_value)
			else:
				self._return_value = new_return_value or self.get("_return_value")

		def compose(fn, *hooks):
			def runner(self, method, *args, **kwargs):
				add_to_return_value(self, fn(self, *args, **kwargs))
				for f in hooks:
					add_to_return_value(self, f(self, method, *args, **kwargs))

				return self._return_value

			return runner

		def composer(self, *args, **kwargs):
			hooks = []
			method = f.__name__
			doc_events = frappe.get_doc_hooks()
			for handler in doc_events.get(self.doctype, {}).get(method, []) \
				+ doc_events.get("*", {}).get(method, []):
				hooks.append(frappe.get_attr(handler))

			composed = compose(f, *hooks)
			return composed(self, method, *args, **kwargs)

		return composer

	def is_whitelisted(self, method):
		fn = getattr(self, method, None)
		if not fn:
			raise NotFound("Method {0} not found".format(method))
		elif not getattr(fn, "whitelisted", False):
			raise Forbidden("Method {0} not whitelisted".format(method))

	def validate_value(self, fieldname, condition, val2, doc=None, raise_exception=None):
		"""Check that value of fieldname should be 'condition' val2
			else throw Exception."""
		error_condition_map = {
			"in": _("one of"),
			"not in": _("none of"),
			"^": _("beginning with"),
		}

		if not doc:
			doc = self

		val1 = doc.get_value(fieldname)

		df = doc.meta.get_field(fieldname)
		val2 = doc.cast(val2, df)

		if not frappe.compare(val1, condition, val2):
			label = doc.meta.get_label(fieldname)
			condition_str = error_condition_map.get(condition, condition)
			if doc.parentfield:
				msg = _("Incorrect value in row {0}: {1} must be {2} {3}").format(doc.idx, label, condition_str, val2)
			else:
				msg = _("Incorrect value: {0} must be {1} {2}").format(label, condition_str, val2)

			# raise passed exception or True
			msgprint(msg, raise_exception=raise_exception or True)

	def validate_table_has_rows(self, parentfield, raise_exception=None):
		"""Raise exception if Table field is empty."""
		if not (isinstance(self.get(parentfield), list) and len(self.get(parentfield)) > 0):
			label = self.meta.get_label(parentfield)
			frappe.throw(_("Table {0} cannot be empty").format(label), raise_exception or frappe.EmptyTableError)

	def round_floats_in(self, doc, fieldnames=None):
		"""Round floats for all `Currency`, `Float`, `Percent` fields for the given doc.

		:param doc: Document whose numeric properties are to be rounded.
		:param fieldnames: [Optional] List of fields to be rounded."""
		if not fieldnames:
			fieldnames = (df.fieldname for df in
				doc.meta.get("fields", {"fieldtype": ["in", ["Currency", "Float", "Percent"]]}))

		for fieldname in fieldnames:
			doc.set(fieldname, flt(doc.get(fieldname), self.precision(fieldname, doc.parentfield)))

	def get_url(self):
		"""Returns Desk URL for this document. `/desk#Form/{doctype}/{name}`"""
		return "/desk#Form/{doctype}/{name}".format(doctype=self.doctype, name=self.name)

	def add_comment(self, comment_type='Comment', text=None, comment_email=None, link_doctype=None, link_name=None, comment_by=None):
		"""Add a comment to this document.

		:param comment_type: e.g. `Comment`. See Communication for more info."""

		out = frappe.get_doc({
			"doctype":"Comment",
			'comment_type': comment_type,
			"comment_email": comment_email or frappe.session.user,
			"comment_by": comment_by,
			"reference_doctype": self.doctype,
			"reference_name": self.name,
			"content": text or comment_type,
			"link_doctype": link_doctype,
			"link_name": link_name
		}).insert(ignore_permissions=True)
		return out

	def add_seen(self, user=None):
		"""add the given/current user to list of users who have seen this document (_seen)"""
		if not user:
			user = frappe.session.user

		if self.meta.track_seen:
			_seen = self.get('_seen') or []
			_seen = frappe.parse_json(_seen)

			if user not in _seen:
				_seen.append(user)
				frappe.db.set_value(self.doctype, self.name, '_seen', json.dumps(_seen), update_modified=False)
				frappe.local.flags.commit = True

	def add_viewed(self, user=None):
		"""add log to communication when a user views a document"""
		if not user:
			user = frappe.session.user

		if hasattr(self.meta, 'track_views') and self.meta.track_views:
			frappe.get_doc({
				"doctype": "View Log",
				"viewed_by": frappe.session.user,
				"reference_doctype": self.doctype,
				"reference_name": self.name,
			}).insert(ignore_permissions=True)
			frappe.local.flags.commit = True

	def get_signature(self):
		"""Returns signature (hash) for private URL."""
		return hashlib.sha224(get_datetime_str(self.creation).encode()).hexdigest()

	def get_liked_by(self):
		liked_by = getattr(self, "_liked_by", None)
		if liked_by:
			return json.loads(liked_by)
		else:
			return []

	def set_onload(self, key, value):
		if not self.get("__onload"):
			self.set("__onload", frappe._dict())
		self.get("__onload")[key] = value

	def get_onload(self, key=None):
		if not key:
			return self.get("__onload", frappe._dict())

		return self.get('__onload')[key]

	def queue_action(self, action, **kwargs):
		"""Run an action in background. If the action has an inner function,
		like _submit for submit, it will call that instead"""
		# call _submit instead of submit, so you can override submit to call
		# run_delayed based on some action
		# See: Stock Reconciliation
		if hasattr(self, '_' + action):
			action = '_' + action

		if file_lock.lock_exists(self.get_signature()):
			frappe.throw(_('This document is currently queued for execution. Please try again'),
				title=_('Document Queued'))

		self.lock()
		enqueue('frappe.model.document.execute_action', doctype=self.doctype, name=self.name,
			action=action, **kwargs)

	def lock(self, timeout=None):
		"""Creates a lock file for the given document. If timeout is set,
		it will retry every 1 second for acquiring the lock again

		:param timeout: Timeout in seconds, default 0"""
		signature = self.get_signature()
		if file_lock.lock_exists(signature):
			lock_exists = True
			if timeout:
				for i in range(timeout):
					time.sleep(1)
					if not file_lock.lock_exists(signature):
						lock_exists = False
						break
			if lock_exists:
				raise frappe.DocumentLockedError
		file_lock.create_lock(signature)

	def unlock(self):
		"""Delete the lock file for this document"""
		file_lock.delete_lock(self.get_signature())

	# validation helpers
	def validate_from_to_dates(self, from_date_field, to_date_field):
		"""
		Generic validation to verify date sequence
		"""
		if date_diff(self.get(to_date_field), self.get(from_date_field)) < 0:
			frappe.throw(_('{0} must be after {1}').format(
				frappe.bold(self.meta.get_label(to_date_field)),
				frappe.bold(self.meta.get_label(from_date_field)),
			), frappe.exceptions.InvalidDates)

	def get_assigned_users(self):
		assignments = frappe.get_all('ToDo',
			fields=['owner'],
			filters={
				'reference_type': self.doctype,
				'reference_name': self.name,
				'status': ('!=', 'Cancelled'),
			})

		users = set([assignment.owner for assignment in assignments])
		return users

def execute_action(doctype, name, action, **kwargs):
	"""Execute an action on a document (called by background worker)"""
	doc = frappe.get_doc(doctype, name)
	doc.unlock()
	try:
		getattr(doc, action)(**kwargs)
	except Exception:
		frappe.db.rollback()

		# add a comment (?)
		if frappe.local.message_log:
			msg = json.loads(frappe.local.message_log[-1]).get('message')
		else:
			msg = '<pre><code>' + frappe.get_traceback() + '</pre></code>'

		doc.add_comment('Comment', _('Action Failed') + '<br><br>' + msg)
		doc.notify_update()


def make_event_update_log(doc, update_type):
	"""Save update info for doctypes that have event consumers"""
	if update_type != 'Delete':
		# diff for update type, doc for create type
		data = frappe.as_json(doc) if not doc.get('diff') else frappe.as_json(doc.diff)
	else:
		data = None
	log_doc = frappe.get_doc({
		'doctype': 'Event Update Log',
		'update_type': update_type,
		'ref_doctype': doc.doctype,
		'docname': doc.name,
		'data': data
	})
	log_doc.insert(ignore_permissions=True)
	frappe.db.commit()


def check_doctype_has_consumers(doctype):
	"""Check if doctype has event consumers for event streaming"""
	if not frappe.db.exists('DocType', 'Event Consumer'):
		return False

	event_consumers = frappe.get_all('Event Consumer Document Type', {
		'ref_doctype': doctype,
		'status': 'Approved'
	}, limit=1)

	if len(event_consumers) and event_consumers[0]:
		return True
	return False
