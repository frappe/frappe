# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

from frappe.utils import strip_html
from frappe.website.utils import scrub_relative_urls
from jinja2.utils import concat
from jinja2 import meta
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
			out[block] = scrub_relative_urls(concat(render(template.new_context(context))))

	_render_blocks(context["template"])

	# default blocks if not found
	if "title" not in out and out.get("header"):
		out["title"] = out["header"]

	if "title" not in out:
		out["title"] = context.get("title")

	if "header" not in out and out.get("title"):
		out["header"] = out["title"]

	if out.get("header") and not out["header"].startswith("<h"):
		out["header"] = "<h2>" + out["header"] + "</h2>"

	if "breadcrumbs" not in out:
		out["breadcrumbs"] = scrub_relative_urls(
			frappe.get_template("templates/includes/breadcrumbs.html").render(context))

	if "meta_block" not in out:
		out["meta_block"] = frappe.get_template("templates/includes/meta_block.html").render(context)


	out["no_sidebar"] = context.get("no_sidebar", 0)

	if "<!-- no-sidebar -->" in out.get("content", ""):
		out["no_sidebar"] = 1

	if "<!-- title:" in out.get("content", ""):
		out["title"] = re.findall('<!-- title:([^>]*) -->', out.get("content"))[0].strip()

	if "{index}" in out.get("content", "") and context.get("children"):
		html = frappe.get_template("templates/includes/static_index.html").render({
				"items": context["children"]})
		out["content"] = out["content"].replace("{index}", html)

	if "{next}" in out.get("content", ""):
		next_item = context.get_next()
		if next_item:
			if next_item.name[0]!="/": next_item.name = "/" + next_item.name
			html = '''<p><br><a href="{name}" class="btn btn-primary">
				{page_title} <i class="icon-chevron-right"></i></a>
			</p>'''.format(**next_item)
			out["content"] = out["content"].replace("{next}", html)

	if "sidebar" not in out and not out.get("no_sidebar"):
		out["sidebar"] = scrub_relative_urls(
			frappe.get_template("templates/includes/sidebar.html").render(context))

	out["title"] = strip_html(out.get("title") or "")

	# remove style and script tags from blocks
	out["style"] = re.sub("</?style[^<>]*>", "", out.get("style") or "")
	out["script"] = re.sub("</?script[^<>]*>", "", out.get("script") or "")

	return out
