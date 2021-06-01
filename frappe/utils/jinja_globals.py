# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt


def resolve_class(classes):
	if classes is None:
		return ""

	if isinstance(classes, str):
		return classes

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
	from frappe import throw, _dict, _
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
	for script in out.scripts:
		html += "<script>{}</script>".format(script)

	return html


def include_script(path):
	path = bundled_asset(path)
	return f'<script type="text/javascript" src="{path}"></script>'


def include_style(path):
	path = bundled_asset(path)
	return f'<link type="text/css" rel="stylesheet" href="{path}">'


def bundled_asset(path):
	from frappe.utils import get_assets_json
	from frappe.website.utils import abs_url

	if ".bundle." in path and not path.startswith("/assets"):
		bundled_assets = get_assets_json()
		path = bundled_assets.get(path) or path

	return abs_url(path)
