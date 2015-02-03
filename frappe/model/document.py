# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _, msgprint
from frappe.utils import flt, cint, cstr, now
from frappe.modules import load_doctype_module
from frappe.model.base_document import BaseDocument
from frappe.model.naming import set_new_name
from werkzeug.exceptions import NotFound, Forbidden

# once_only validation
# methods

def get_doc(arg1, arg2=None):
	if isinstance(arg1, BaseDocument):
		return arg1
	elif isinstance(arg1, basestring):
		doctype = arg1
	else:
		doctype = arg1.get("doctype")

	controller = get_controller(doctype)
	if controller:
		return controller(arg1, arg2)

	raise ImportError, arg1

_classes = {}

def get_controller(doctype):
	if not doctype in _classes:
		module = load_doctype_module(doctype)
		classname = doctype.replace(" ", "").replace("-", "")
		if hasattr(module, classname):
			_class = getattr(module, classname)
			if issubclass(_class, Document):
				_class = getattr(module, classname)
			else:
				raise ImportError, doctype
		else:
			raise ImportError, doctype
		_classes[doctype] = _class

	return _classes[doctype]

class Document(BaseDocument):
	def __init__(self, arg1, arg2=None):
		self.doctype = self.name = None

		if arg1 and isinstance(arg1, basestring):
			if not arg2:
				# single
				self.doctype = self.name = arg1
			else:
				self.doctype = arg1
				if isinstance(arg2, dict):
					# filter
					self.name = frappe.db.get_value(arg1, arg2, "name")
					if self.name is None:
						frappe.throw(_("{0} {1} not found").format(_(arg1), arg2), frappe.DoesNotExistError)
				else:
					self.name = arg2

			self.load_from_db()

		elif isinstance(arg1, dict):
			super(Document, self).__init__(arg1)
			self.init_valid_columns()

		else:
			# incorrect arguments. let's not proceed.
			raise frappe.DataError("Document({0}, {1})".format(arg1, arg2))

		if hasattr(self, "__setup__"):
			self.__setup__()

		self.dont_update_if_missing = []

	def load_from_db(self):
		if not getattr(self, "_metaclass", False) and self.meta.issingle:
			single_doc = frappe.db.get_singles_dict(self.doctype)
			if not single_doc:
				single_doc = frappe.new_doc(self.doctype).as_dict()
				single_doc["name"] = self.doctype
				del single_doc["__islocal"]

			self.update(single_doc)
			self.init_valid_columns()
			self._fix_numeric_types()

		else:
			d = frappe.db.get_value(self.doctype, self.name, "*", as_dict=1)
			if not d:
				frappe.throw(_("{0} {1} not found").format(_(self.doctype), self.name), frappe.DoesNotExistError)
			self.update(d)

		if self.name=="DocType" and self.doctype=="DocType":
			from frappe.model.meta import doctype_table_fields
			table_fields = doctype_table_fields
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

	def check_permission(self, permtype, permlabel=None):
		if not self.has_permission(permtype):
			self.raise_no_permission_to(permlabel or permtype)

	def has_permission(self, permtype):
		if getattr(self, "ignore_permissions", False):
			return True
		return frappe.has_permission(self.doctype, permtype, self)

	def raise_no_permission_to(self, perm_type):
		raise frappe.PermissionError("No permission to {} {} {}".format(perm_type, self.doctype, self.name or ""))

	def insert(self, ignore_permissions=None):
		if getattr(self, "in_print", False):
			return

		if ignore_permissions!=None:
			self.ignore_permissions = ignore_permissions

		self.set("__islocal", True)

		self.check_permission("create")
		self._set_defaults()
		self._set_docstatus_user_and_timestamp()
		self.check_if_latest()
		self.set_new_name()
		self.run_method("before_insert")
		self.set_parent_in_children()

		self.set("__in_insert", True)
		self.run_before_save_methods()
		self._validate()
		self.delete_key("__in_insert")

		# run validate, on update etc.

		# parent
		if getattr(self.meta, "issingle", 0):
			self.update_single(self.get_valid_dict())
		else:
			self.db_insert()

		# children
		for d in self.get_all_children():
			d.db_insert()

		self.run_method("after_insert")
		self.set("__in_insert", True)
		self.run_post_save_methods()
		self.delete_key("__in_insert")

		return self

	def save(self, ignore_permissions=None):
		if getattr(self, "in_print", False):
			return

		if ignore_permissions!=None:
			self.ignore_permissions = ignore_permissions

		if self.get("__islocal") or not self.get("name"):
			self.insert()
			return

		self.check_permission("write", "save")

		self._set_docstatus_user_and_timestamp()
		self.check_if_latest()
		self.set_parent_in_children()
		self.run_before_save_methods()

		if self._action != "cancel":
			self._validate()

		if self._action == "update_after_submit":
			self.validate_update_after_submit()

		# parent
		if self.meta.issingle:
			self.update_single(self.get_valid_dict())
		else:
			self.db_update()

		# children
		child_map = {}
		ignore_children_type = self.get("ignore_children_type") or []

		for d in self.get_all_children():
			d.db_update()
			child_map.setdefault(d.doctype, []).append(d.name)

		for df in self.meta.get_table_fields():
			if df.options not in ignore_children_type:
				cnames = child_map.get(df.options) or []
				if cnames:
					frappe.db.sql("""delete from `tab%s` where parent=%s and parenttype=%s and
						name not in (%s)""" % (df.options, '%s', '%s', ','.join(['%s'] * len(cnames))),
							tuple([self.name, self.doctype] + cnames))
				else:
					frappe.db.sql("""delete from `tab%s` where parent=%s and parenttype=%s""" \
						% (df.options, '%s', '%s'), (self.name, self.doctype))

		self.run_post_save_methods()

		return self

	def set_new_name(self):
		set_new_name(self)
		# set name for children
		for d in self.get_all_children():
			set_new_name(d)

	def update_single(self, d):
		frappe.db.sql("""delete from tabSingles where doctype=%s""", self.doctype)
		for field, value in d.iteritems():
			if field != "doctype":
				frappe.db.sql("""insert into tabSingles(doctype, field, value)
					values (%s, %s, %s)""", (self.doctype, field, value))

	def _set_docstatus_user_and_timestamp(self):
		self._original_modified = self.modified
		self.modified = now()
		self.modified_by = frappe.session.user
		if not self.creation:
			self.creation = self.modified
		if not self.owner:
			self.owner = self.modified_by
		if self.docstatus==None:
			self.docstatus=0

		for d in self.get_all_children():
			d.docstatus = self.docstatus
			d.modified = self.modified
			d.modified_by = self.modified_by
			if not d.owner:
				d.owner = self.owner
			if not d.creation:
				d.creation = self.creation

	def _validate(self):
		self._validate_mandatory()
		self._validate_links()
		self._validate_selects()
		self._validate_constants()
		for d in self.get_all_children():
			d._validate_selects()
			d._validate_constants()

		self._extract_images_from_text_editor()

	def _set_defaults(self):
		if frappe.flags.in_import:
			return

		new_doc = frappe.new_doc(self.doctype)
		self.update_if_missing(new_doc)

		# children
		for df in self.meta.get_table_fields():
			new_doc = frappe.new_doc(df.options)
			value = self.get(df.fieldname)
			if isinstance(value, list):
				for d in value:
					d.update_if_missing(new_doc)

	def check_if_latest(self):
		conflict = False
		self._action = "save"
		if not self.get('__islocal'):
			if self.meta.issingle:
				modified = frappe.db.get_value(self.doctype, self.name, "modified")
				if cstr(modified) and cstr(modified) != cstr(self._original_modified):
					conflict = True
			else:
				tmp = frappe.db.get_value(self.doctype, self.name,
					["modified", "docstatus"], as_dict=True)

				if not tmp:
					frappe.throw(_("Record does not exist"))

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
		if not self.docstatus:
			self.docstatus = 0
		if docstatus==0:
			if self.docstatus==0:
				self._action = "save"
			elif self.docstatus==1:
				self._action = "submit"
				self.check_permission("submit")
			else:
				raise frappe.DocstatusTransitionError("Cannot change docstatus from 0 to 2")

		elif docstatus==1:
			if self.docstatus==1:
				self._action = "update_after_submit"
				self.check_permission("submit")
			elif self.docstatus==2:
				self._action = "cancel"
				self.check_permission("cancel")
			else:
				raise frappe.DocstatusTransitionError("Cannot change docstatus from 1 to 0")

		elif docstatus==2:
			raise frappe.ValidationError

	def set_parent_in_children(self):
		for d in self.get_all_children():
			d.parent = self.name
			d.parenttype = self.doctype

	def validate_update_after_submit(self):
		if getattr(self, "ignore_validate_update_after_submit", False):
			return

		self._validate_update_after_submit()
		for d in self.get_all_children():
			d._validate_update_after_submit()

		# TODO check only allowed values are updated

	def _validate_mandatory(self):
		if self.get("ignore_mandatory"):
			return

		missing = self._get_missing_mandatory_fields()
		for d in self.get_all_children():
			missing.extend(d._get_missing_mandatory_fields())

		if not missing:
			return

		for fieldname, msg in missing:
			msgprint(msg)

		raise frappe.MandatoryError(", ".join((each[0] for each in missing)))

	def _validate_links(self):
		if self.get("ignore_links"):
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
		ret = []
		for df in self.meta.get("fields", {"fieldtype": "Table"}):
			if parenttype:
				if df.options==parenttype:
					return self.get(df.fieldname)
			value = self.get(df.fieldname)
			if isinstance(value, list):
				ret.extend(value)
		return ret

	def _extract_images_from_text_editor(self):
		from frappe.utils.file_manager import extract_images_from_html
		if self.doctype != "DocType":
			for df in self.meta.get("fields", {"fieldtype":"Text Editor"}):
				extract_images_from_html(self, df.fieldname)

	def run_method(self, method, *args, **kwargs):
		"""run standard triggers, plus those in frappe"""
		if hasattr(self, method) and hasattr(getattr(self, method), "__call__"):
			fn = lambda self, *args, **kwargs: getattr(self, method)(*args, **kwargs)
		else:
			# hack! to run hooks even if method does not exist
			fn = lambda self, *args, **kwargs: None

		fn.__name__ = method.encode("utf-8")
		return Document.hook(fn)(self, *args, **kwargs)

	@staticmethod
	def whitelist(f):
		f.whitelisted = True
		return f

	@whitelist.__func__
	def submit(self):
		self.docstatus = 1
		self.save()

	@whitelist.__func__
	def cancel(self):
		self.docstatus = 2
		self.save()

	def delete(self):
		frappe.delete_doc(self.doctype, self.name)

	def run_before_save_methods(self):
		if getattr(self, "ignore_validate", False):
			return

		if self._action=="save":
			self.run_method("validate")
			self.run_method("before_save")
		elif self._action=="submit":
			self.run_method("validate")
			self.run_method("before_submit")
		elif self._action=="cancel":
			self.run_method("before_cancel")
		elif self._action=="update_after_submit":
			self.run_method("before_update_after_submit")

	def run_post_save_methods(self):
		if self._action=="save":
			self.run_method("on_update")
		elif self._action=="submit":
			self.run_method("on_update")
			self.run_method("on_submit")
			self.add_comment("Submitted")
		elif self._action=="cancel":
			self.run_method("on_cancel")
			self.check_no_back_links_exist()
			self.add_comment("Cancelled")
		elif self._action=="update_after_submit":
			self.run_method("on_update_after_submit")


	def check_no_back_links_exist(self):
		from frappe.model.delete_doc import check_if_doc_is_linked
		if not self.get("ignore_links"):
			check_if_doc_is_linked(self, method="Cancel")

	@staticmethod
	def hook(f):
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
			doc_events = frappe.get_hooks("doc_events", {})
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
		"""check that value of fieldname should be 'condition' val2
			else throw exception"""
		error_condition_map = {
			"in": _("one of"),
			"not in": _("none of"),
			"^": _("beginning with"),
		}

		if not doc:
			doc = self

		df = doc.meta.get_field(fieldname)

		val1 = doc.get(fieldname)

		if df.fieldtype in ("Currency", "Float", "Percent"):
			val1 = flt(val1, self.precision(df.fieldname, doc.parentfield or None))
			val2 = flt(val2, self.precision(df.fieldname, doc.parentfield or None))
		elif df.fieldtype in ("Int", "Check"):
			val1 = cint(val1)
			val2 = cint(val2)
		elif df.fieldtype in ("Data", "Text", "Small Text", "Long Text",
			"Text Editor", "Select", "Link", "Dynamic Link"):
				val1 = cstr(val1)
				val2 = cstr(val2)

		if not frappe.compare(val1, condition, val2):
			label = doc.meta.get_label(fieldname)
			condition_str = error_condition_map.get(condition, condition)
			if doc.parentfield:
				msg = _("Incorrect value in row {0}: {1} must be {2} {3}".format(doc.idx, label, condition_str, val2))
			else:
				msg = _("Incorrect value: {0} must be {1} {2}".format(label, condition_str, val2))

			# raise passed exception or True
			msgprint(msg, raise_exception=raise_exception or True)

	def validate_table_has_rows(self, parentfield, raise_exception=None):
		if not (isinstance(self.get(parentfield), list) and len(self.get(parentfield)) > 0):
			label = self.meta.get_label(parentfield)
			frappe.throw(_("Table {0} cannot be empty").format(label), raise_exception or frappe.EmptyTableError)

	def round_floats_in(self, doc, fieldnames=None):
		if not fieldnames:
			fieldnames = (df.fieldname for df in
				doc.meta.get("fields", {"fieldtype": ["in", ["Currency", "Float", "Percent"]]}))

		for fieldname in fieldnames:
			doc.set(fieldname, flt(doc.get(fieldname), self.precision(fieldname, doc.parentfield)))

	def precision(self, fieldname, parentfield=None):
		from frappe.model.meta import get_field_precision

		if parentfield and not isinstance(parentfield, basestring):
			parentfield = parentfield.parentfield

		cache_key = parentfield or "main"

		if not hasattr(self, "_precision"):
			self._precision = frappe._dict()

		if cache_key not in self._precision:
			self._precision[cache_key] = frappe._dict()

		if fieldname not in self._precision[cache_key]:
			self._precision[cache_key][fieldname] = None

			doctype = self.meta.get_field(parentfield).options if parentfield else self.doctype
			df = frappe.get_meta(doctype).get_field(fieldname)

			if df.fieldtype in ("Currency", "Float", "Percent"):
				self._precision[cache_key][fieldname] = get_field_precision(df, self)

		return self._precision[cache_key][fieldname]

	def get_url(self):
		return "/desk#Form/{doctype}/{name}".format(doctype=self.doctype, name=self.name)

	def add_comment(self, comment_type, text=None):
		comment = frappe.get_doc({
			"doctype":"Comment",
			"comment_by": frappe.session.user,
			"comment_type": comment_type,
			"comment_doctype": self.doctype,
			"comment_docname": self.name,
			"comment": text or _(comment_type)
		}).insert(ignore_permissions=True)
		return comment
