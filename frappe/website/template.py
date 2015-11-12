# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

from frappe.utils import strip_html
from frappe.website.utils import get_full_index
from frappe import _
from jinja2.utils import concat
from jinja2 import meta
import re

def build_template(context):
	"""Returns a dict of block name and its rendered content"""

	out = {}
	render_blocks(context["template"], out, context)

	# set_sidebar(out, context)
	set_breadcrumbs(out, context)
	set_title_and_header(out, context)

	# meta
	if "meta_block" not in out:
		out["meta_block"] = frappe.get_template("templates/includes/meta_block.html").render(context)

	add_index(out, context)

	# render
	content_context = {}
	content_context.update(context)
	content_context.update(out)
	out["content"] = frappe.get_template("templates/includes/page_content.html").render(content_context)

	separate_style_and_script(out, context)
	add_hero(out, context)

	return out

def render_blocks(template_path, out, context):
	"""Build the template block by block from the main template."""
	env = frappe.get_jenv()
	source = frappe.local.jloader.get_source(frappe.local.jenv, template_path)[0]
	for referenced_template_path in meta.find_referenced_templates(env.parse(source)):
		if referenced_template_path:
			render_blocks(referenced_template_path, out, context)

	template = frappe.get_template(template_path)
	for block, render in template.blocks.items():
		new_context = template.new_context(context)
		out[block] = concat(render(new_context))

def separate_style_and_script(out, context):
	"""Extract `style` and `script` tags into separate blocks"""
	out["style"] = re.sub("</?style[^<>]*>", "", out.get("style") or "")
	out["script"] = re.sub("</?script[^<>]*>", "", out.get("script") or "")

def set_breadcrumbs(out, context):
	"""Build breadcrumbs template (deprecated)"""
	out["no_breadcrumbs"] = context.get("no_breadcrumbs", 0) \
		or ("<!-- no-breadcrumbs -->" in out.get("content", ""))

	if out["no_breadcrumbs"]:
		out["breadcrumbs"] = ""

	elif "breadcrumbs" not in out:
		out["breadcrumbs"] = frappe.get_template("templates/includes/breadcrumbs.html").render(context)

def set_title_and_header(out, context):
	"""Extract and set title and header from content or context."""
	out["no_header"] = context.get("no_header", 0) or ("<!-- no-header -->" in out.get("content", ""))

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


def set_sidebar(out, context):
	"""Include sidebar (deprecated)"""
	out["has_sidebar"] = not (context.get("no_sidebar", 0) or ("<!-- no-sidebar -->" in out.get("content", "")))

	if out.get("has_sidebar"):
		out["sidebar"] = frappe.get_template("templates/includes/sidebar.html").render(context)

def add_index(out, context):
	"""Add index, next button if `{index}`, `{next}` is present."""
	# table of contents

	extn = ""
	if context.page_links_with_extn:
		extn = ".html"

	if "{index}" in out.get("content", "") and context.get("children") and len(context.children):
		full_index = get_full_index(context.pathname, extn = extn)

		if full_index:
			html = frappe.get_template("templates/includes/full_index.html").render({
					"full_index": full_index,
					"url_prefix": context.url_prefix
				})

			out["content"] = out["content"].replace("{index}", html)

	# next and previous
	if "{next}" in out.get("content", ""):
		next_item = context.doc.get_next()
		next_item.extn = "" if context.doc.has_children(next_item.name) else extn
		if context.relative_links:
			next_item.name = next_item.page_name or ""
		else:
			if next_item and next_item.name and next_item.name[0]!="/":
				next_item.name = "/" + next_item.name

		if next_item and next_item.name:
			if not next_item.title:
				next_item.title = ""
			html = ('<p class="btn-next-wrapper"><a class="btn-next" href="{name}{extn}">'\
				+_("Next")+': {title}</a></p>').format(**next_item)
		else:
			html = ""

		out["content"] = out["content"].replace("{next}", html)

def add_hero(out, context):
	"""Add a hero element if specified in content or hooks.
	Hero elements get full page width."""
	out["hero"] = ""
	if "<!-- start-hero -->" in out["content"]:
		parts1 = out["content"].split("<!-- start-hero -->")
		parts2 = parts1[1].split("<!-- end-hero -->")
		out["content"] = parts1[0] + parts2[1]
		out["hero"] = parts2[0]

	elif context.hero and context.hero.get(context.pathname):
		out["hero"] = frappe.render_template(context.hero[context.pathname][0], context)
