# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import webnotes
from webnotes.webutils import get_access, can_cache
from webnotes.templates.website_group.post import clear_post_cache

doctype = "Website Group"
no_cache = 1

def get_context(context):
	bean = context.bean
	group, view = guess_group_view(bean, context)
	
	try:
		if not has_access(context.access, view):
			raise webnotes.PermissionError
			
		group_context = get_group_context(group, view, bean, context)
		group_context.update(context)
	
		return group_context
	
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
		
def get_group_context(group, view, bean, context):
	cache_key = "website_group_context:{}:{}".format(group, view)
	views = get_views(bean.doc.group_type)
	view = webnotes._dict(views.get(view))
	
	if can_cache(view.get("no_cache")):
		group_context = webnotes.cache().get_value(cache_key)
		if group_context:
			return group_context
			
	group_context = build_group_context(group, view, bean, views, context)
	
	if can_cache(view.get("no_cache")):
		webnotes.cache().set_value(cache_key, group_context)
		
	return group_context
	
def build_group_context(group, view, bean, views, context):
	title = "{} - {}".format(bean.doc.group_title, view.get("label"))
	
	for name, opts in views.iteritems():
		opts["url"] = opts["url"].format(pathname=context.pathname, post="")
	
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
	
def has_access(access, view):	
	if view=="settings":
		return access.get("admin")
	elif view in ("add", "edit"):
		return access.get("write")
	else:
		return access.get("read")
		
def clear_cache(page_name=None, website_group=None):
	if page_name or website_group:
		filters = {"page_name": page_name} if page_name else website_group

		website_group = webnotes.conn.get_value("Website Group", filters,
			["page_name", "group_type"], as_dict=True)

		if not website_group:
			return

		website_groups = [website_group]
	else:
		clear_post_cache()
		website_groups = webnotes.conn.sql("""select page_name, group_type from `tabWebsite Group`""", as_dict=True)
	
	cache = webnotes.cache()
	for group in website_groups:
		for view in get_views(group.group_type):
			cache.delete_value("website_group_context:{}:{}".format(group.page_name, view))

def clear_event_cache():
	for group in webnotes.conn.sql_list("""select name from `tabWebsite Group` where group_type='Event'"""):
			clear_unit_views(website_group=group)
