# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import frappe
from frappe import _, msgprint
from frappe.utils import cint, flt, cstr, now
from frappe.modules import load_doctype_module
from frappe.model.base_document import BaseDocument

# once_only validation
# methods

def get_doc(arg1, arg2=None):
	if isinstance(arg1, basestring):
		doctype = arg1
	else:
		doctype = arg1.get("doctype")
		
	module = load_doctype_module(doctype)
	classname = doctype.replace(" ", "")
	if hasattr(module, classname):
		_class = getattr(module, classname)
		if issubclass(_class, Document):
			return getattr(module, classname)(arg1, arg2)
	
	return Document(arg1, arg2)

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
						raise frappe.DoesNotExistError
				else:
					self.name = arg2
					
			self.load_from_db()

		elif isinstance(arg1, dict):
			super(Document, self).__init__(arg1)
		
		else:
			# incorrect arguments. let's not proceed.
			raise frappe.DataError("Document({0}, {1})".format(arg1, arg2))

	def load_from_db(self):
		if not getattr(self, "_metaclass", False) and self.meta.issingle:
			self.update(frappe.db.get_singles_dict(self.doctype))
			self._fix_numeric_types()
		
		else:
			d = frappe.db.get_value(self.doctype, self.name, "*", as_dict=1)
			self.update(d, valid_columns = d.keys())

			for df in self.get_table_fields():
				children = frappe.db.get_values(df.options, 
					{"parent": self.name, "parenttype": self.doctype, "parentfield": df.fieldname}, 
					"*", as_dict=True)
				if children:
					self.set(df.fieldname, children, children[0].keys())
				else:
					self.set(df.fieldname, [])
			
	def get_table_fields(self):
		return self.meta.get('fields', {"fieldtype":"Table"})

	def has_permission(self, permtype):
		if getattr(self, "_ignore_permissions", False):
			return True
		return frappe.has_permission(self.doctype, permtype, self)
					
	def insert(self):
		# check links
		# check permissions
		self.set("__islocal", True)
		
		if not self.has_permission("create"):
			raise frappe.PermissionError
		self._set_defaults()
		self._set_docstatus_user_and_timestamp()
		self._check_if_latest()
		self.run_method("before_insert")
		self.run_before_save_methods()
		self._validate()
		
		# run validate, on update etc.
		
		# parent
		if self.meta.issingle:
			self.update_single(self.get_valid_dict())
		else:
			self.db_insert()
		
		# children
		for d in self.get_all_children():
			d.parent = self.name
			d.db_insert()
		self.run_method("after_insert")
		self.run_post_save_methods()

	def save(self):
		if self.get("__islocal") or not self.get("name"):
			self.insert()
			return

		if not self.has_permission("write"):
			raise frappe.PermissionError

		self._set_docstatus_user_and_timestamp()
		self._check_if_latest()
		self.run_before_save_methods()
		self._validate()

		# parent
		if self.meta.issingle:
			self.update_single(self.get_valid_dict())
		else:
			self.db_update()

		# children
		ignore_children_type = self.get("_ignore_children_type", [])
		for d in self.get_all_children():
			if d.doctype not in _ignore_children_type:
				d.parent = self.name
				d.db_update()
		
		self.run_post_save_methods()
		
	def update_single(self, d):
		frappe.db.sql("""delete from tabSingles where doctype=%s""", self.doctype)
		for field, value in d.iteritems():
			if field not in ("doctype"):
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
		self._validate_constants()
		for d in self.get_all_children():
			d._validate_constants()
		self._extract_images_from_text_editor()
			
	def _set_defaults(self):
		if frappe.flags.in_import:
			return
		
		new_doc = frappe.new_doc(self.doctype).fields
		self.set_missing_values(new_doc)

		# children
		for df in self.meta.get("fields", {"fieldtype":"Table"}):
			new_doc = frappe.new_doc(df.options).fields
			value = self.get(df.fieldname)
			if isinstance(value, list):
				for d in value:
					d.set_missing_values(new_doc)
										
	def _check_if_latest(self):
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
					frappe.msgprint("""This record does not exist. Please refresh.""", raise_exception=1)

				modified = cstr(tmp.modified)
								
				if modified and modified != cstr(self._original_modified):
					conflict = True
			
				self.check_docstatus_transition(tmp.docstatus)
				
			if conflict:
				frappe.msgprint(_("Error: Document has been modified after you have opened it") \
				+ (" (%s, %s). " % (modified, self.modified)) \
				+ _("Please refresh to get the latest document."), 
					raise_exception=frappe.TimestampMismatchError)

	def check_docstatus_transition(self, docstatus):
		if not self.docstatus:
			self.docstatus = 0
		if docstatus==0:
			if self.docstatus==0:
				self._action = "save"
			elif self.docstatus==1:
				self._action = "submit"
				if not self.has_permission("submit"):
					raise frappe.PermissionError
			else:
				raise frappe.DocstatusTransitionError
		
		elif docstatus==1:
			if self.docstatus==1:
				self._action = "update_after_submit"
				self.validate_update_after_submit()
				if not self.has_permission("submit"):
					raise frappe.PermissionError
			elif self.docstatus==2:
				self._action = "cancel"
				if not self.has_permission("cancel"):
					raise frappe.PermissionError
			else:
				raise frappe.DocstatusTransitionError
				
		elif docstatus==2:
			raise frappe.ValidationError
	
	def validate_update_after_submit(self):
		# check only allowed values are updated
		pass
	
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
		
		invalid_links = self.get_invalid_links()
		for d in self.get_all_children():
			invalid_links.extend(d.get_invalid_links())
		
		if not invalid_links:
			return
			
		msg = ", ".join((each[2] for each in invalid_links))
		frappe.throw("{}: {}".format(_("Could not find the following documents"), msg),
			frappe.LinkValidationError)
			
	def get_all_children(self):
		ret = []
		for df in self.meta.get("fields", {"fieldtype": "Table"}):
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
		def add_to_response(out, new_response):
			if isinstance(new_response, dict):
				out.update(new_response)

		if hasattr(self, method):
			add_to_response(frappe.local.response, 
				getattr(self, method)(*args, **kwargs))	

		args = [self, method] + list(args or [])

		for handler in frappe.get_hooks("bean_event:" + self.doctype + ":" + method) \
			+ frappe.get_hooks("bean_event:*:" + method):
			add_to_response(frappe.local.response, 
				frappe.call(frappe.get_attr(handler), *args, **kwargs))
		
		return frappe.local.response

	def run_before_save_methods(self):
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
		elif self._action=="cancel":
			self.run_method("on_cancel")
		elif self._action=="update_after_submit":
			self.run_method("on_update_after_submit")
