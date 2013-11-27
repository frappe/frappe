# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import webnotes
import webnotes.model.meta
import webnotes.defaults
from webnotes.utils.file_manager import remove_all
from webnotes import _

def delete_doc(doctype=None, name=None, doclist = None, force=0, ignore_doctypes=[], for_reload=False, ignore_permissions=False):
	"""
		Deletes a doc(dt, dn) and validates if it is not submitted and not linked in a live record
	"""

	# get from form
	if not doctype:
		doctype = webnotes.form_dict.get('dt')
		name = webnotes.form_dict.get('dn')
	
	if not doctype:
		webnotes.msgprint('Nothing to delete!', raise_exception =1)

	# already deleted..?
	if not webnotes.conn.exists(doctype, name):
		return

	if not for_reload:
		check_permission_and_not_submitted(doctype, name, ignore_permissions)
		
		run_on_trash(doctype, name, doclist)
		# check if links exist
		if not force:
			check_if_doc_is_linked(doctype, name)
		
	try:
		tablefields = webnotes.model.meta.get_table_fields(doctype)
		webnotes.conn.sql("delete from `tab%s` where name=%s" % (doctype, "%s"), name)
		for t in tablefields:
			if t[0] not in ignore_doctypes:
				webnotes.conn.sql("delete from `tab%s` where parent = %s" % (t[0], '%s'), name)
	except Exception, e:
		if e.args[0]==1451:
			webnotes.msgprint("Cannot delete %s '%s' as it is referenced in another record. You must delete the referred record first" % (doctype, name))
		
		raise
		
	# delete attachments
	remove_all(doctype, name)
	
	# delete restrictions
	webnotes.defaults.clear_default(parenttype="Restriction", key=doctype, value=name)
		
	return 'okay'

def check_permission_and_not_submitted(doctype, name, ignore_permissions=False):
	# permission
	if not ignore_permissions and webnotes.session.user!="Administrator" and not webnotes.has_permission(doctype, "cancel"):
		webnotes.msgprint(_("User not allowed to delete."), raise_exception=True)

	# check if submitted
	if webnotes.conn.get_value(doctype, name, "docstatus") == 1:
		webnotes.msgprint(_("Submitted Record cannot be deleted")+": "+name+"("+doctype+")",
			raise_exception=True)

def run_on_trash(doctype, name, doclist):
	# call on_trash if required
	if doclist:
		bean = webnotes.bean(doclist)
	else:
		bean = webnotes.bean(doctype, name)
		
	bean.run_method("on_trash")

class LinkExistsError(webnotes.ValidationError): pass

def check_if_doc_is_linked(dt, dn, method="Delete"):
	"""
		Raises excption if the given doc(dt, dn) is linked in another record.
	"""
	from webnotes.model.rename_doc import get_link_fields
	link_fields = get_link_fields(dt)
	link_fields = [[lf['parent'], lf['fieldname'], lf['issingle']] for lf in link_fields]

	for link_dt, link_field, issingle in link_fields:
		if not issingle:
			item = webnotes.conn.get_value(link_dt, {link_field:dn}, 
				["name", "parent", "parenttype", "docstatus"], as_dict=True)
			
			if item and item.parent != dn and (method=="Delete" or 
					(method=="Cancel" and item.docstatus==1)):
				webnotes.msgprint(method + " " + _("Error") + ":"+\
					("%s (%s) " % (dn, dt)) + _("is linked in") + (" %s (%s)") % 
					(item.parent or item.name, item.parent and item.parenttype or link_dt),
					raise_exception=LinkExistsError)
