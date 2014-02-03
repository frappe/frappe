# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import webnotes
from webnotes.webutils import get_access, render_blocks, can_cache

doctype = "Website Group"
no_cache = 1

def get_context(context):
	bean = webnotes.bean(context.ref_doctype, context.docname)
	group, view = guess_group_view(bean, context)
	
	try:
		if not has_access(group, view):
			raise webnotes.PermissionError
			
		group_context = get_group_context(group, view, bean)
		group_context["access"] = get_access(group)
		group_context.update(context)
	
		return render_blocks(group_context)
	
	except webnotes.DoesNotExistError:
		return {
			"content": '<div class="alert alert-danger full-page">'
				'The page you are looking for does not exist.</div>'
			}
	except webnotes.PermissionError:
		return {
			"content": '<div class="alert alert-danger full-page">'
				'You are not permitted to view this page.</div>'
		}
		
def get_group_context(group, view, bean):
	cache_key = "website_group_context:{}:{}".format(group, view)
	views = get_views(bean.doc.group_type)
	view = webnotes._dict(views.get(view))
	
	if can_cache(view.get("no_cache")):
		group_context = webnotes.cache().get_value(cache_key)
		if group_context:
			return group_context
			
	group_context = build_group_context(group, view, bean, views)
	
	if can_cache(view.get("no_cache")):
		webnotes.cache().set_value(cache_key, group_context)
		
	return group_context
	
def build_group_context(group, view, bean, views):
	title = "{} - {}".format(bean.doc.group_title, view.get("label"))
	
	for name, opts in views.iteritems():
		opts["url"] = opts["url"].format(group=group, post="")
	
	group_context = webnotes._dict({
		"group": bean.doc.fields,
		"view": view,
		"views": (v[1] for v in sorted(views.iteritems(), key=lambda (k, v): v.get("idx"))),
		"title": title
	})
	
	handler = get_handler(bean.doc.group_type)
	if handler:
		group_context.update(handler.get_context(group_context))
	
	return group_context

def guess_group_view(bean, context):
	group = context.docname
	view = webnotes.form_dict.view
	
	if not view:
		for v, opts in get_views(bean.doc.group_type).iteritems():
			if opts.get("default"):
				view = v
				break
	
	return group, view
	
def get_handler(group_type):
	handler = webnotes.get_hooks("website_group_handler:{}".format(group_type))
	if handler:
		return webnotes.get_module(handler[0])
	
def get_views(group_type):
	from copy import deepcopy
	handler = get_handler(group_type)
	if handler and hasattr(handler, "get_views"):
		return deepcopy(handler.get_views() or {})
	return {}
	
def has_access(group, view):
	access = get_access(group)
	
	if view=="settings":
		return access.get("admin")
	elif view in ("add", "edit"):
		return access.get("write")
	else:
		return access.get("read")
