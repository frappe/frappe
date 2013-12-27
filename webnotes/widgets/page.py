# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import webnotes
import webnotes.model.doc
import webnotes.model.code

@webnotes.whitelist()
def get(name):
	"""
	   Return the :term:`doclist` of the `Page` specified by `name`
	"""
	page = webnotes.bean("Page", name)
	if has_permission(page.doclist):
		page.run_method("get_from_files")
		return page.doclist
	else:
		webnotes.response['403'] = 1
		raise webnotes.PermissionError, 'No read permission for Page %s' % \
			(page.doclist[0].title or name,)

@webnotes.whitelist(allow_guest=True)
def getpage():
	"""
	   Load the page from `webnotes.form` and send it via `webnotes.response`
	"""
	page = webnotes.form_dict.get('name')
	doclist = get(page)

	if has_permission(doclist):
		# load translations
		if webnotes.lang != "en":
			webnotes.response["__messages"] = webnotes.get_lang_dict("page", page)

		webnotes.response['docs'] = doclist
	else:
		webnotes.response['403'] = 1
		raise webnotes.PermissionError, 'No read permission for Page %s' % \
			(doclist[0].title or page, )
		
def has_permission(page_doclist):
	if webnotes.user.name == "Administrator" or "System Manager" in webnotes.user.get_roles():
		return True
		
	page_roles = [d.role for d in page_doclist if d.fields.get("doctype")=="Page Role"]
	if page_roles:
		if webnotes.session.user == "Guest" and "Guest" not in page_roles:
			return False
		elif not set(page_roles).intersection(set(webnotes.get_roles())):
			# check if roles match
			return False
		
	if not webnotes.has_permission("Page", ptype="read", refdoc=page_doclist[0].name):
		# check if there are any restrictions
		return False
	else:
		# hack for home pages! if no page roles, allow everyone to see!
		return True
