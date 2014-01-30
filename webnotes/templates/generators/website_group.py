# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import webnotes
from webnotes.webutils import get_access

doctype = "Website Group"
no_cache = 1

def get_context(controller, page_options):
	group, view = guess_group_view(controller, page_options)
	
	try:
		if not has_access(group, view):
			raise webnotes.PermissionError
	
		context = get_initial_context(group, view, controller)
		context["access"] = get_access(group)
		context["content"] = get_content(context)
	
		return context
	
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
		
def get_initial_context(group, view, controller):
	def _get_initial_context():
		if controller:
			group = controller.doc
		else:
			group = webnotes.doc("Website Group", group)
		
		# move all this to webutils
		
		
		parents = webnotes.conn.sql("""select name, unit_title from tabUnit 
			where lft < %s and rgt > %s order by lft asc""", (unit.lft, unit.rgt), as_dict=1)
		
		# update title
		title = unit.unit_title
		views = get_views(unit)
		view_options = views.get(view, {})
		if view_options:
			title += " - " + view_options["label"]
		
		views = sorted([opts for v, opts in views.items()], key=lambda d: d.get("idx"))
		context = {
			"name": unit.name,
			"public_read": unit.public_read,
			"title": "Aam Aadmi Party: " + title,
			"unit_title": title,
			"public_write": unit.public_write,
			"parents": parents,
			"children": get_child_unit_items(unit.name, public_read=1),
			"unit": unit.fields,
			"view": view,
			"views": views,
			"view_options": view_options
		}
		return context

	if webnotes.conf.get("disable_website_cache"):
		return _get_unit_context(unit, view)	
	
	return webnotes.cache().get_value("unit_context:{unit}:{view}".format(unit=unit.lower(), view=view), 
		lambda:_get_unit_context(unit, view))
	
def get_content(context):
	pass

def guess_group_view(controller, page_options):
	group = page_options.docname
	
	view = None
	pathname = webnotes.request.path[1:]
	if "/" in pathname:
		view = pathname.split("/", 1)[1]
		
	if not view:
		get_views = webnotes.get_hooks("website_group_views:{}".controller.doc.group_type)
		if get_views:
			for v, opts in webnotes.get_attr(get_views)(group).items():
				if opts.get("default"):
					view = v
					break

	return group, view
	
def has_access(group, view):
	access = get_access(group)
	
	if view=="settings":
		return access.get("admin")
	elif view in ("add", "edit"):
		return access.get("write")
	else:
		return access.get("read")