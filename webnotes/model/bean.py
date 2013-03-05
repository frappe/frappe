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

from __future__ import unicode_literals
"""
Transactions are defined as collection of classes, a Bean represents collection of Document
objects for a transaction with main and children.

Group actions like save, etc are performed on doclists
"""

import webnotes
from webnotes import _
from webnotes.utils import cint
from webnotes.model.doc import Document

class DocstatusTransitionError(webnotes.ValidationError): pass

class Bean:
	"""
	Collection of Documents with one parent and multiple children
	"""
	def __init__(self, dt=None, dn=None):
		self.docs = []
		self.obj = None
		self.ignore_permissions = False
		self.ignore_children_type = []
		self.ignore_check_links = False
		self.ignore_validate = False
		
		if isinstance(dt, basestring) and not dn:
			dn = dt
		if dt and dn:
			self.load_from_db(dt, dn)
		elif isinstance(dt, list):
			self.set_doclist(dt)
		elif isinstance(dt, dict):
			self.set_doclist([dt])

	def load_from_db(self, dt=None, dn=None, prefix='tab'):
		"""
			Load doclist from dt
		"""
		from webnotes.model.doc import Document, getchildren

		if not dt: dt = self.doc.doctype
		if not dn: dn = self.doc.name

		doc = Document(dt, dn, prefix=prefix)

		# get all children types
		tablefields = webnotes.model.meta.get_table_fields(dt)

		# load chilren
		doclist = webnotes.doclist([doc,])
		for t in tablefields:
			doclist += getchildren(doc.name, t[0], t[1], dt, prefix=prefix)

		self.set_doclist(doclist)
		self.run_method("onload")

	def __iter__(self):
		return self.docs.__iter__()

	def from_compressed(self, data, docname):
		from webnotes.model.utils import expand
		self.docs = expand(data)
		self.set_doclist(self.docs)
		
	def set_doclist(self, docs):
		for i, d in enumerate(docs):
			if isinstance(d, dict):
				docs[i] = Document(fielddata=d)
		
		self.docs = self.doclist = webnotes.doclist(docs)
		self.doc, self.children = self.doclist[0], self.doclist[1:]
		if self.obj:
			self.obj.doclist = self.doclist
			self.obj.doc = self.doc

	def make_obj(self):
		if self.obj: return self.obj
		self.obj = webnotes.get_obj(doc=self.doc, doclist=self.doclist)
		self.controller = self.obj
		return self.obj

	def to_dict(self):
		return [d.fields for d in self.docs]

	def check_if_latest(self, method="save"):
		from webnotes.model.meta import is_single

		if not cint(self.doc.fields.get('__islocal')) and not is_single(self.doc.doctype):
			tmp = webnotes.conn.sql("""
				SELECT modified, docstatus FROM `tab%s` WHERE name="%s" for update"""
				% (self.doc.doctype, self.doc.name), as_dict=True)

			if not tmp:
				webnotes.msgprint("""This record does not exist. Please refresh.""", raise_exception=1)

			if tmp and str(tmp[0].modified) != str(self.doc.modified):
				webnotes.msgprint("""
				Document has been modified after you have opened it.
				To maintain the integrity of the data, you will not be able to save your changes.
				Please refresh this document. [%s/%s]""" % (tmp[0].modified, self.doc.modified), raise_exception=1)
			
			self.check_docstatus_transition(tmp[0].docstatus, method)
			
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
		if self.ignore_check_links:
			return
		ref, err_list = {}, []
		for d in self.docs:
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

		for d in self.docs:
			if self.doc.fields.get('__islocal'):
				d.owner = user
				d.creation = ts

			d.modified_by = user
			d.modified = ts
			if d.docstatus != 2 and self.to_docstatus >= d.docstatus: # don't update deleted
				d.docstatus = self.to_docstatus

	def prepare_for_save(self, method):
		self.check_if_latest(method)
		if method != "cancel":
			self.check_links()
		self.update_timestamps_and_docstatus()
		self.update_parent_info()

	def update_parent_info(self):
		idx_map = {}
		is_local = cint(self.doc.fields.get("__islocal"))
		
		for i, d in enumerate(self.doclist[1:]):
			if d.parentfield:
				d.parenttype = self.doc.doctype
				d.parent = self.doc.name
			if not d.idx:
				d.idx = idx_map.setdefault(d.parentfield, 0) + 1
			if is_local:
				# if parent is new, all children should be new
				d.fields["__islocal"] = 1
			
			idx_map[d.parentfield] = d.idx

	def run_method(self, method):
		self.make_obj()
		
		if hasattr(self.obj, method):
			getattr(self.obj, method)()
		if hasattr(self.obj, 'custom_' + method):
			getattr(self.obj, 'custom_' + method)()

		notify(self.obj, method)
		
		self.set_doclist(self.obj.doclist)

	def get_method(self, method):
		self.make_obj()
		return getattr(self.obj, method, None)

	def save_main(self):
		try:
			self.doc.save(check_links = False)
		except NameError, e:
			webnotes.msgprint('%s "%s" already exists' % (self.doc.doctype, self.doc.name))

			# prompt if cancelled
			if webnotes.conn.get_value(self.doc.doctype, self.doc.name, 'docstatus')==2:
				webnotes.msgprint('[%s "%s" has been cancelled]' % (self.doc.doctype, self.doc.name))
			webnotes.errprint(webnotes.utils.getTraceback())
			raise e

	def save_children(self):
		child_map = {}
		for d in self.children:
			if d.fields.get("parent") or d.fields.get("parentfield"):
				d.parent = self.doc.name # rename if reqd
				d.parenttype = self.doc.doctype
				
				d.save(check_links=False)
			
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

	def insert(self):
		self.doc.fields["__islocal"] = 1
		return self.save()
	
	def has_read_perm(self):
		return webnotes.has_permission(self.doc.doctype, "read", self.doc)
	
	def save(self, check_links=1):
		if self.ignore_permissions or webnotes.has_permission(self.doc.doctype, "write", self.doc):
			self.to_docstatus = 0
			self.prepare_for_save("save")
			if not self.ignore_validate:
				self.run_method('validate')
			self.save_main()
			self.save_children()
			self.run_method('on_update')
		else:
			self.no_permission_to(_("Write"))
		
		return self

	def submit(self):
		if self.ignore_permissions or webnotes.has_permission(self.doc.doctype, "submit", self.doc):
			self.to_docstatus = 1
			self.prepare_for_save("submit")
			self.run_method('validate')
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

	def no_permission_to(self, ptype):
		webnotes.msgprint(("%s (%s): " % (self.doc.name, _(self.doc.doctype))) + \
			_("No Permission to ") + ptype, raise_exception=True)
			
	def check_no_back_links_exist(self):
		from webnotes.model.utils import check_if_doc_is_linked
		check_if_doc_is_linked(self.doc.doctype, self.doc.name, method="Cancel")


def clone(source_wrapper):
	""" Copy previous invoice and change dates"""
	if isinstance(source_wrapper, list):
		source_wrapper = Bean(source_wrapper)
	
	new_wrapper = Bean(source_wrapper.doclist.copy())
	new_wrapper.doc.fields.update({
		"amended_from": None,
		"amendment_date": None,
	})
	
	for d in new_wrapper.doclist:
		d.fields.update({
			"name": None,
			"__islocal": 1,
			"docstatus": 0,
		})
	
	return new_wrapper


def notify(controller, caller_method):
	try:
		from startup.observers import observer_map
	except ImportError:
		return
		
	doctype = controller.doc.doctype
	
	def call_observers(key):
		if key in observer_map:
			observer_list = observer_map[key]
			if isinstance(observer_list, basestring):
				observer_list = [observer_list]
			for observer_method in observer_list:
				webnotes.get_method(observer_method)(controller, caller_method)
	
	call_observers("*:*")
	call_observers(doctype + ":*")
	call_observers("*:" + caller_method)
	call_observers(doctype + ":" + caller_method)

# for bc
def getlist(doclist, parentfield):
	"""
		Return child records of a particular type
	"""
	import webnotes.model.utils
	return webnotes.model.utils.getlist(doclist, parentfield)

def copy_doclist(doclist, no_copy = []):
	"""
		Make a copy of the doclist
	"""
	import webnotes.model.utils
	return webnotes.model.utils.copy_doclist(doclist, no_copy)

