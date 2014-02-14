# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes

from webnotes.website.utils import scrub_relative_urls
from jinja2.utils import concat
from jinja2 import meta

def render_blocks(context):
	"""returns a dict of block name and its rendered content"""

	out = {}
	
	env = webnotes.get_jenv()
		
	def _render_blocks(template_path):
		source = webnotes.local.jloader.get_source(webnotes.local.jenv, template_path)[0]
		for referenced_template_path in meta.find_referenced_templates(env.parse(source)):
			if referenced_template_path:
				_render_blocks(referenced_template_path)
				
		template = webnotes.get_template(template_path)
		for block, render in template.blocks.items():
			out[block] = scrub_relative_urls(concat(render(template.new_context(context))))
	
	_render_blocks(context["template_path"])

	# default blocks if not found
	if "title" not in out:
		out["title"] = context.get("title")
	
	if "header" not in out:
		out["header"] = out["title"]

	if not out["header"].startswith("<h"):
		out["header"] = "<h2>" + out["header"] + "</h2>"
		
	if "breadcrumbs" not in out:
		out["breadcrumbs"] = scrub_relative_urls(
			webnotes.get_template("templates/includes/breadcrumbs.html").render(context))
		
	if "sidebar" not in out:
		out["sidebar"] = scrub_relative_urls(
			webnotes.get_template("templates/includes/sidebar.html").render(context))

	return out
