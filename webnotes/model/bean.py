# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
"""
Transactions are defined as collection of classes, a Bean represents collection of Document
objects for a transaction with main and children.

Group actions like save, etc are performed on doclists
"""

import webnotes
from webnotes import _, msgprint
from webnotes.utils import cint, cstr, flt
from webnotes.model.doc import Document

class DocstatusTransitionError(webnotes.ValidationError): pass
class BeanPermissionError(webnotes.ValidationError): pass
class TimestampMismatchError(webnotes.ValidationError): pass

class Bean:
	"""
	Collection of Documents with one parent and multiple children
	"""
	def __init__(self, dt=None, dn=None):
		self.obj = None
		self.ignore_permissions = False
		self.ignore_children_type = []
		self.ignore_links = False
		self.ignore_validate = False
		self.ignore_fields = False
		self.ignore_mandatory = False
		
		if isinstance(dt, basestring) and not dn:
			dn = dt
		if dt and dn:
			self.load_from_db(dt, dn)
		elif isinstance(dt, list):
			self.set_doclist(dt)
		elif isinstance(dt, dict):
			self.set_doclist([dt])

	def load_from_db(self, dt=None, dn=None):
		"""
			Load doclist from dt
		"""
		from webnotes.model.doc import getchildren

		if not dt: dt = self.doc.doctype
		if not dn: dn = self.doc.name

		doc = Document(dt, dn)
		
		# get all children types
		tablefields = webnotes.model.meta.get_table_fields(dt)

		# load chilren
		doclist = webnotes.doclist([doc,])
		for t in tablefields:
			doclist += getchildren(doc.name, t[0], t[1], dt)

		self.set_doclist(doclist)
		
		if dt == dn:
			self.convert_type(self.doc)

	def __iter__(self):
		return self.doclist.__iter__()

	@property
	def meta(self):
		if not hasattr(self, "_meta"):
			self._meta = webnotes.get_doctype(self.doc.doctype)
		return self._meta

	def from_compressed(self, data, docname):
		from webnotes.model.utils import expand
		self.set_doclist(expand(data))
		
	def set_doclist(self, doclist):
		for i, d in enumerate(doclist):
			if isinstance(d, dict):
				doclist[i] = Document(fielddata=d)
		
		self.doclist = webnotes.doclist(doclist)
		self.doc = self.doclist[0]
		if self.obj:
			self.obj.doclist = self.doclist
			self.obj.doc = self.doc

	def make_controller(self):
		if self.obj:
			# update doclist before running any method
			self.obj.doclist = self.doclist
			return self.obj
		
		self.obj = webnotes.get_obj(doc=self.doc, doclist=self.doclist)
		self.obj.bean = self
		self.controller = self.obj
		return self.obj

	def get_controller(self):
		return self.make_controller()

	def to_dict(self):
		return [d.fields for d in self.doclist]

	def check_if_latest(self, method="save"):
		from webnotes.model.meta import is_single

		conflict = False
		if not cint(self.doc.fields.get('__islocal')):
			if is_single(self.doc.doctype):
				modified = webnotes.conn.get_value(self.doc.doctype, self.doc.name, "modified")
				if isinstance(modified, list):
					modified = modified[0]
				if cstr(modified) and cstr(modified) != cstr(self.doc.modified):
					conflict = True
			else:
				tmp = webnotes.conn.sql("""select modified, docstatus from `tab%s` 
					where name="%s" for update"""
					% (self.doc.doctype, self.doc.name), as_dict=True)

				if not tmp:
					webnotes.msgprint("""This record does not exist. Please refresh.""", raise_exception=1)

				modified = cstr(tmp[0].modified)
				if modified and modified != cstr(self.doc.modified):
					conflict = True
			
				self.check_docstatus_transition(tmp[0].docstatus, method)
				
			if conflict:
				webnotes.msgprint(_("Error: Document has been modified after you have opened it") \
				+ (" (%s, %s). " % (modified, self.doc.modified)) \
				+ _("Please refresh to get the latest document."), raise_exception=TimestampMismatchError)
				
	def check_docstatus_transition(self, db_docstatus, method):
		valid = {
			"save": [0,0],
			"submit": [0,1],
			"cancel": [1,2],
			"update_after_submit": [1,1]
		}
		
		labels = {
			0: _("Draft"),
			1: _("Submitted"),
			2: _("Cancelled")
		}
		
		if not hasattr(self, "to_docstatus"):
			self.to_docstatus = 0
		
		if method != "runserverobj" and [db_docstatus, self.to_docstatus] != valid[method]:
			webnotes.msgprint(_("Cannot change from") + ": " + labels[db_docstatus] + " > " + \
				labels[self.to_docstatus], raise_exception=DocstatusTransitionError)

	def check_links(self):
		if self.ignore_links:
			return
		ref, err_list = {}, []
		for d in self.doclist:
			if not ref.get(d.doctype):
				ref[d.doctype] = d.make_link_list()

			err_list += d.validate_links(ref[d.doctype])

		if err_list:
			webnotes.msgprint("""[Link Validation] Could not find the following values: %s.
			Please correct and resave. Document Not Saved.""" % ', '.join(err_list), raise_exception=1)

	def update_timestamps_and_docstatus(self):
		from webnotes.utils import now
		ts = now()
		user = webnotes.__dict__.get('session', {}).get('user') or 'Administrator'

		for d in self.doclist:
			if self.doc.fields.get('__islocal'):
				if not d.owner:
					d.owner = user
				if not d.creation:
					d.creation = ts

			d.modified_by = user
			d.modified = ts
			if d.docstatus != 2 and self.to_docstatus >= int(d.docstatus): # don't update deleted
				d.docstatus = self.to_docstatus

	def prepare_for_save(self, method):
		self.check_if_latest(method)
		
		self.update_timestamps_and_docstatus()
		self.update_parent_info()
		
		if self.doc.fields.get("__islocal"):
			# set name before validate
			self.doc.set_new_name(self.get_controller())
			self.run_method('before_insert')
			
		if method != "cancel":
			self.extract_images_from_text_editor()
			self.check_links()

	def update_parent_info(self):
		idx_map = {}
		is_local = cint(self.doc.fields.get("__islocal"))
		
		if not webnotes.flags.in_import:
			parentfields = [d.fieldname for d in self.meta.get({"doctype": "DocField", "fieldtype": "Table"})]
			
		for i, d in enumerate(self.doclist[1:]):
			if d.parentfield:
				if not webnotes.flags.in_import:
					if not d.parentfield in parentfields:
						webnotes.msgprint("Bad parentfield %s" % d.parentfield, 
							raise_exception=True)
				d.parenttype = self.doc.doctype
				d.parent = self.doc.name
			if not d.idx:
				d.idx = idx_map.setdefault(d.parentfield, 0) + 1
			else:
				d.idx = cint(d.idx)
			if is_local:
				# if parent is new, all children should be new
				d.fields["__islocal"] = 1
				d.name = None
			
			idx_map[d.parentfield] = d.idx

	def run_method(self, method, *args, **kwargs):
		self.make_controller()
		
		if hasattr(self.controller, method):
			getattr(self.controller, method)(*args, **kwargs)
		if hasattr(self.controller, 'custom_' + method):
			getattr(self.controller, 'custom_' + method)(*args, **kwargs)

		notify(self, method)
		
		self.set_doclist(self.controller.doclist)
		
	def get_attr(self, method):
		self.make_controller()
		return getattr(self.controller, method, None)

	def insert(self):
		self.doc.fields["__islocal"] = 1
			
		self.set_defaults()
		
		if webnotes.flags.in_test:
			if self.meta.get_field("naming_series"):
				self.doc.naming_series = "_T-" + self.doc.doctype + "-"
		
		return self.save()
	
	def insert_or_update(self):
		if self.doc.name and webnotes.conn.exists(self.doc.doctype, self.doc.name):
			return self.save()
		else:
			return self.insert()
	
	def set_defaults(self):
		if webnotes.flags.in_import:
			return
			
		new_docs = {}
		new_doclist = []
		
		for d in self.doclist:
			if not d.doctype in new_docs:
				new_docs[d.doctype] = webnotes.new_doc(d.doctype)
				
			newd = webnotes.doc(new_docs[d.doctype].fields.copy())
			newd.fields.update(d.fields)
			new_doclist.append(newd)
			
		self.set_doclist(new_doclist)

	def has_read_perm(self):
		return webnotes.has_permission(self.doc.doctype, "read", self.doc)
	
	def save(self, check_links=1):
		perm_to_check = "write"
		if self.doc.fields.get("__islocal"):
			perm_to_check = "create"
			if not self.doc.owner:
				self.doc.owner = webnotes.session.user
				
		if self.ignore_permissions or webnotes.has_permission(self.doc.doctype, perm_to_check, self.doc):
			self.to_docstatus = 0
			self.prepare_for_save("save")
			if not self.ignore_validate:
				self.run_method('validate')
			if not self.ignore_mandatory:
				self.check_mandatory()
			self.save_main()
			self.save_children()
			self.run_method('on_update')
			if perm_to_check=="create":
				self.run_method("after_insert")
		else:
			self.no_permission_to(_(perm_to_check.title()))
		
		return self

	def submit(self):
		if self.ignore_permissions or webnotes.has_permission(self.doc.doctype, "submit", self.doc):
			self.to_docstatus = 1
			self.prepare_for_save("submit")
			self.run_method('validate')
			self.check_mandatory()
			self.save_main()
			self.save_children()
			self.run_method('on_update')
			self.run_method('on_submit')
		else:
			self.no_permission_to(_("Submit"))
			
		return self

	def cancel(self):
		if self.ignore_permissions or webnotes.has_permission(self.doc.doctype, "cancel", self.doc):
			self.to_docstatus = 2
			self.prepare_for_save("cancel")
			self.run_method('before_cancel')
			self.save_main()
			self.save_children()
			self.run_method('on_cancel')
			self.check_no_back_links_exist()
		else:
			self.no_permission_to(_("Cancel"))
			
		return self

	def update_after_submit(self):
		if self.doc.docstatus != 1:
			webnotes.msgprint("Only to called after submit", raise_exception=1)
		if self.ignore_permissions or webnotes.has_permission(self.doc.doctype, "write", self.doc):
			self.to_docstatus = 1
			self.prepare_for_save("update_after_submit")
			self.run_method('before_update_after_submit')
			self.save_main()
			self.save_children()
			self.run_method('on_update_after_submit')
		else:
			self.no_permission_to(_("Update"))
		
		return self

	def save_main(self):
		try:
			self.doc.save(check_links = False, ignore_fields = self.ignore_fields)
		except NameError, e:
			webnotes.msgprint('%s "%s" already exists' % (self.doc.doctype, self.doc.name))

			# prompt if cancelled
			if webnotes.conn.get_value(self.doc.doctype, self.doc.name, 'docstatus')==2:
				webnotes.msgprint('[%s "%s" has been cancelled]' % (self.doc.doctype, self.doc.name))
			webnotes.errprint(webnotes.utils.get_traceback())
			raise

	def save_children(self):
		child_map = {}
		for d in self.doclist[1:]:
			if d.fields.get("parent") or d.fields.get("parentfield"):
				d.parent = self.doc.name # rename if reqd
				d.parenttype = self.doc.doctype
				
				d.save(check_links=False, ignore_fields = self.ignore_fields)
			
			child_map.setdefault(d.doctype, []).append(d.name)
		
		# delete all children in database that are not in the child_map
		
		# get all children types
		tablefields = webnotes.model.meta.get_table_fields(self.doc.doctype)
				
		for dt in tablefields:
			if dt[0] not in self.ignore_children_type:
				cnames = child_map.get(dt[0]) or []
				if cnames:
					webnotes.conn.sql("""delete from `tab%s` where parent=%s and parenttype=%s and
						name not in (%s)""" % (dt[0], '%s', '%s', ','.join(['%s'] * len(cnames))), 
							tuple([self.doc.name, self.doc.doctype] + cnames))
				else:
					webnotes.conn.sql("""delete from `tab%s` where parent=%s and parenttype=%s""" \
						% (dt[0], '%s', '%s'), (self.doc.name, self.doc.doctype))
	
	def delete(self):
		webnotes.delete_doc(self.doc.doctype, self.doc.name)

	def no_permission_to(self, ptype):
		webnotes.msgprint(("%s (%s): " % (self.doc.name, _(self.doc.doctype))) + \
			_("No Permission to ") + ptype, raise_exception=BeanPermissionError)
			
	def check_no_back_links_exist(self):
		from webnotes.model.utils import check_if_doc_is_linked
		check_if_doc_is_linked(self.doc.doctype, self.doc.name, method="Cancel")
		
	def check_mandatory(self):
		missing = []
		for doc in self.doclist:
			for df in self.meta:
				if df.doctype=="DocField" and df.reqd and df.parent==doc.doctype and df.fieldname!="naming_series":
					msg = ""
					if df.fieldtype == "Table":
						if not self.doclist.get({"parentfield": df.fieldname}):
							msg = _("Error") + ": " + _("Data missing in table") + ": " + _(df.label)
				
					elif doc.fields.get(df.fieldname) is None:
						msg = _("Error") + ": "
						if doc.parentfield:
							msg += _("Row") + (" # %s: " % (doc.idx,))
			
						msg += _("Value missing for") + ": " + _(df.label)
					
					if msg:
						missing.append([msg, df.fieldname])
		
		if missing:
			for msg, fieldname in missing:
				msgprint(msg)

			raise webnotes.MandatoryError, ", ".join([fieldname for msg, fieldname in missing])
			
	def convert_type(self, doc):
		if doc.doctype==doc.name and doc.doctype!="DocType":
			for df in self.meta.get({"doctype": "DocField", "parent": doc.doctype}):
				if df.fieldtype in ("Int", "Check"):
					doc.fields[df.fieldname] = cint(doc.fields.get(df.fieldname))
				elif df.fieldtype in ("Float", "Currency"):
					doc.fields[df.fieldname] = flt(doc.fields.get(df.fieldname))
				
			doc.docstatus = cint(doc.docstatus)
			
	def extract_images_from_text_editor(self):
		from webnotes.utils.file_manager import extract_images_from_html
		if self.doc.doctype != "DocType":
			for df in self.meta.get({"doctype": "DocField", "parent": self.doc.doctype, "fieldtype":"Text Editor"}):
				extract_images_from_html(self.doc, df.fieldname)

def clone(source_wrapper):
	""" make a clone of a document"""
	if isinstance(source_wrapper, list):
		source_wrapper = Bean(source_wrapper)
	
	new_wrapper = Bean(source_wrapper.doclist.copy())
	
	if new_wrapper.doc.fields.get("amended_from"):
		new_wrapper.doc.fields["amended_from"] = None

	if new_wrapper.doc.fields.get("amendment_date"):
		new_wrapper.doc.fields["amendment_date"] = None
	
	for d in new_wrapper.doclist:
		d.fields.update({
			"name": None,
			"__islocal": 1,
			"docstatus": 0,
		})
	
	return new_wrapper

def notify(bean, caller):
	for hook in webnotes.get_hooks().bean_event or []:
		doctype, trigger, handler = hook.split(":")
		if ((doctype=="*") or (doctype==bean.doc.doctype)) and caller==trigger:
			webnotes.get_attr(handler)(bean, trigger)

# for bc
def getlist(doclist, parentfield):
	import webnotes.model.utils
	return webnotes.model.utils.getlist(doclist, parentfield)

def copy_doclist(doclist, no_copy = []):
	"""
		Make a copy of the doclist
	"""
	import webnotes.model.utils
	return webnotes.model.utils.copy_doclist(doclist, no_copy)

