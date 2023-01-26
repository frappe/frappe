# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE


def resolve_class(*classes):
	if classes and len(classes) == 1:
		classes = classes[0]

	if classes is None:
		return ""
	if classes is False:
		return ""

	if isinstance(classes, (list, tuple)):
		return " ".join(resolve_class(c) for c in classes).strip()

	if isinstance(classes, dict):
		return " ".join(classname for classname in classes if classes[classname]).strip()

	return classes


def inspect(var, render=True):
	from frappe.utils.jinja import get_jenv

	context = {"var": var}
	if render:
		html = "<pre>{{ var | pprint | e }}</pre>"
	else:
		return ""
	return get_jenv().from_string(html).render(context)


def web_block(template, values=None, **kwargs):
	options = {"template": template, "values": values}
	options.update(kwargs)
	return web_blocks([options])


def web_blocks(blocks):
	import frappe
	from frappe import _, _dict, throw
	from frappe.website.doctype.web_page.web_page import get_web_blocks_html

	web_blocks = []
	for block in blocks:
		if not block.get("template"):
			throw(_("Web Template is not specified"))

		doc = _dict(
			{
				"doctype": "Web Page Block",
				"web_template": block["template"],
				"web_template_values": block.get("values", {}),
				"add_top_padding": 1,
				"add_bottom_padding": 1,
				"add_container": 1,
				"hide_block": 0,
				"css_class": "",
			}
		)
		doc.update(block)
		web_blocks.append(doc)

	out = get_web_blocks_html(web_blocks)

	html = out.html

	if not frappe.flags.web_block_scripts:
		frappe.flags.web_block_scripts = {}
		frappe.flags.web_block_styles = {}

	for template, scripts in out.scripts.items():
		# deduplication of scripts when web_blocks methods are used in web pages
		# see render_dynamic method web_page.py
		if template not in frappe.flags.web_block_scripts:
			for script in scripts:
				html += f"<script data-web-template='{template}'>{script}</script>"
			frappe.flags.web_block_scripts[template] = True

	for template, styles in out.styles.items():
		# deduplication of styles when web_blocks methods are used in web pages
		# see render_dynamic method web_page.py
		if template not in frappe.flags.web_block_styles:
			for style in styles:
				html += f"<style data-web-template='{template}'>{style}</style>"
			frappe.flags.web_block_styles[template] = True

	return html


def get_dom_id(seed=None):
	from frappe import generate_hash

	return "id-" + generate_hash(12)


def include_script(path, preload=True):
	"""Get path of bundled script files.

	If preload is specified the path will be added to preload headers so browsers can prefetch
	assets."""
	path = bundled_asset(path)

	if preload:
		import frappe

		frappe.local.preload_assets["script"].append(path)

	return f'<script type="text/javascript" src="{path}"></script>'


def include_style(path, rtl=None, preload=True):
	"""Get path of bundled style files.

	If preload is specified the path will be added to preload headers so browsers can prefetch
	assets."""
	path = bundled_asset(path)

	if preload:
		import frappe

		frappe.local.preload_assets["style"].append(path)

	return f'<link type="text/css" rel="stylesheet" href="{path}">'


def bundled_asset(path, rtl=None):
	from frappe.utils import get_assets_json
	from frappe.website.utils import abs_url

	if ".bundle." in path and not path.startswith("/assets"):
		bundled_assets = get_assets_json()
		if path.endswith(".css") and is_rtl(rtl):
			path = f"rtl_{path}"
		path = bundled_assets.get(path) or path

	return abs_url(path)


def is_rtl(rtl=None):
	from frappe import local

	if rtl is None:
		return local.lang in ["ar", "he", "fa", "ps"]
	return rtl
