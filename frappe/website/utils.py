# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, re, os

def delete_page_cache(path):
	cache = frappe.cache()
	groups = ("page_context", "website_page", "sitemap_options")
	if path:
		for name in groups:
			cache.hdel(name, path)
	else:
		for name in groups:
			cache.delete_key(name)

def find_first_image(html):
	m = re.finditer("""<img[^>]*src\s?=\s?['"]([^'"]*)['"]""", html)
	try:
		return m.next().groups()[0]
	except StopIteration:
		return None

def can_cache(no_cache=False):
	return not (frappe.conf.disable_website_cache or getattr(frappe.local, "no_cache", False) or no_cache)

def get_comment_list(doctype, name):
	return frappe.db.sql("""select
		comment, comment_by_fullname, creation, comment_by
		from `tabComment` where comment_doctype=%s
		and ifnull(comment_type, "Comment")="Comment"
		and comment_docname=%s order by creation""", (doctype, name), as_dict=1) or []

def get_home_page():
	if frappe.local.flags.home_page:
		return frappe.local.flags.home_page

	def _get_home_page():
		role_home_page = frappe.get_hooks("role_home_page")
		home_page = None

		if role_home_page:
			for role in frappe.get_roles():
				if role in role_home_page:
					home_page = role_home_page[role][-1]
					break

		if not home_page:
			home_page = frappe.get_hooks("home_page")
			if home_page:
				home_page = home_page[-1]

		if not home_page:
			home_page = frappe.db.get_value("Website Settings", None, "home_page") or "login"

		return home_page

	return frappe.cache().hget("home_page", frappe.session.user, _get_home_page)

def is_signup_enabled():
	if getattr(frappe.local, "is_signup_enabled", None) is None:
		frappe.local.is_signup_enabled = True
		if frappe.utils.cint(frappe.db.get_value("Website Settings",
			"Website Settings", "disable_signup")):
				frappe.local.is_signup_enabled = False

	return frappe.local.is_signup_enabled

def cleanup_page_name(title):
	"""make page name from title"""
	if not title:
		return title

	name = title.lower()
	name = re.sub('[~!@#$%^&*+()<>,."\'\?]', '', name)
	name = re.sub('[:/]', '-', name)

	name = '-'.join(name.split())

	# replace repeating hyphens
	name = re.sub(r"(-)\1+", r"\1", name)

	return name


def get_shade(color, percent):
	color, color_format = detect_color_format(color)
	r, g, b, a = color

	avg = (float(int(r) + int(g) + int(b)) / 3)
	# switch dark and light shades
	if avg > 128:
		percent = -percent

	# stronger diff for darker shades
	if percent < 25 and avg < 64:
		percent = percent * 2

	new_color = []
	for channel_value in (r, g, b):
		new_color.append(get_shade_for_channel(channel_value, percent))

	r, g, b = new_color

	return format_color(r, g, b, a, color_format)


def detect_color_format(color):
	if color.startswith("rgba"):
		color_format = "rgba"
		color = [c.strip() for c in color[5:-1].split(",")]

	elif color.startswith("rgb"):
		color_format = "rgb"
		color = [c.strip() for c in color[4:-1].split(",")] + [1]

	else:
		# assume hex
		color_format = "hex"

		if color.startswith("#"):
			color = color[1:]

		if len(color) == 3:
			# hex in short form like #fff
			color = "{0}{0}{1}{1}{2}{2}".format(*tuple(color))

		color = [int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16), 1]

	return color, color_format


def get_shade_for_channel(channel_value, percent):
	v = int(channel_value) + int(int('ff', 16) * (float(percent)/100))
	if v < 0:
		v=0
	if v > 255:
		v=255

	return v


def format_color(r, g, b, a, color_format):
	if color_format == "rgba":
		return "rgba({0}, {1}, {2}, {3})".format(r, g, b, a)

	elif color_format == "rgb":
		return "rgb({0}, {1}, {2})".format(r, g, b)

	else:
		# assume hex
		return "#{0}{1}{2}".format(convert_to_hex(r), convert_to_hex(g), convert_to_hex(b))


def convert_to_hex(channel_value):
	h = hex(channel_value)[2:]

	if len(h) < 2:
		h = "0" + h

	return h

def abs_url(path):
	"""Deconstructs and Reconstructs a URL into an absolute URL or a URL relative from root '/'"""
	if not path:
		return
	if path.startswith('http://') or path.startswith('https://'):
		return path
	if not path.startswith("/"):
		path = "/" + path
	return path

def get_full_index(route=None, doctype="Web Page", extn = False):
	"""Returns full index of the website (on Web Page) upto the n-th level"""
	all_routes = []

	def get_children(parent):
		children = frappe.db.get_all(doctype, ["parent_website_route", "page_name", "title", "template_path"],
			{"parent_website_route": parent}, order_by="idx asc")
		for d in children:
			d.url = abs_url(os.path.join(d.parent_website_route or "", d.page_name))
			if d.url not in all_routes:
				d.children = get_children(d.url.lstrip("/"))
				all_routes.append(d.url)

			if extn and os.path.basename(d.template_path).split(".")[0] != "index":
				d.url = d.url + ".html"

		# no index.html for home page
		# home should not be in table of contents
		if not parent:
			children = [d for d in children if d.page_name not in ("index.html", "index",
				"", "contents")]

		return children

	return get_children(route or "")

