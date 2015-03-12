# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

from frappe.utils import strip_html
from frappe import _
from frappe.website.utils import scrub_relative_urls
from jinja2.utils import concat
from jinja2 import meta
from markdown2 import markdown
import re

def render_blocks(context):
	"""returns a dict of block name and its rendered content"""

	out = {}

	env = frappe.get_jenv()

	def _render_blocks(template_path):
		source = frappe.local.jloader.get_source(frappe.local.jenv, template_path)[0]
		for referenced_template_path in meta.find_referenced_templates(env.parse(source)):
			if referenced_template_path:
				_render_blocks(referenced_template_path)

		template = frappe.get_template(template_path)
		for block, render in template.blocks.items():
			new_context = template.new_context(context)
			out[block] = scrub_relative_urls(concat(render(new_context)))

	_render_blocks(context["template"])

	out["has_sidebar"] = not (context.get("no_sidebar", 0) or ("<!-- no-sidebar -->" in out.get("content", "")))

	if out.get("has_sidebar"):
		out["sidebar"] = frappe.get_template("templates/includes/sidebar.html").render(context)

	out["no_breadcrumbs"] = context.get("no_breadcrumbs", 0) or ("<!-- no-breadcrumbs -->" in out.get("content", ""))
	out["no_header"] = context.get("no_header", 0) or ("<!-- no-header -->" in out.get("content", ""))

	# default blocks if not found

	# title
	if "<!-- title:" in out.get("content", ""):
		out["title"] = re.findall('<!-- title:([^>]*) -->', out.get("content"))[0].strip()

	if "title" not in out:
		out["title"] = context.get("title")

	if context.get("page_titles") and context.page_titles.get(context.pathname):
		out["title"] = context.page_titles.get(context.pathname)[0]

	# header
	if out["no_header"]:
		out["header"] = ""
	else:
		if "title" not in out and out.get("header"):
			out["title"] = out["header"]

		if not out.get("header") and "<h1" not in out.get("content", ""):
			if out.get("title"):
				out["header"] = out["title"]

		if out.get("header") and not re.findall("<h.>", out["header"]):
			out["header"] = "<h1>" + out["header"] + "</h1>"

	if not out.get("header"):
		out["no_header"] = 1

	out["title"] = strip_html(out.get("title") or "")

	# breadcrumbs
	if not out["no_breadcrumbs"] and "breadcrumbs" not in out:
		out["breadcrumbs"] = scrub_relative_urls(
			frappe.get_template("templates/includes/breadcrumbs.html").render(context))

	# meta
	if "meta_block" not in out:
		out["meta_block"] = frappe.get_template("templates/includes/meta_block.html").render(context)

	# table of contents
	if "{index}" in out.get("content", "") and context.get("children"):
		html = frappe.get_template("templates/includes/static_index.html").render({
				"items": context["children"]})

		out["content"] = out["content"].replace("{index}", html)

	# next and previous
	if "{next}" in out.get("content", ""):
		next_item = context.doc.get_next()
		if next_item:
			if next_item.name[0]!="/": next_item.name = "/" + next_item.name
			html = ('<p><br><a href="{name}">'+_("Next")+': {title}</a></p>').format(**next_item)
			out["content"] = out["content"].replace("{next}", html)

	# remove style and script tags from blocks
	out["style"] = re.sub("</?style[^<>]*>", "", out.get("style") or "")
	out["script"] = re.sub("</?script[^<>]*>", "", out.get("script") or "")

	# render
	content_context = {}
	content_context.update(context)
	content_context.update(out)
	out["content"] = frappe.get_template("templates/includes/page_content.html").render(content_context)

	# extract hero (if present)
	out["hero"] = ""
	if "<!-- start-hero -->" in out["content"]:
		parts1 = out["content"].split("<!-- start-hero -->")
		parts2 = parts1[1].split("<!-- end-hero -->")
		out["content"] = parts1[0] + parts2[1]
		out["hero"] = parts2[0]

	elif context.hero and context.hero.get(context.pathname):
		out["hero"] = frappe.render_template(context.hero[context.pathname][0], context)

	return out
