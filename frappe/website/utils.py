# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, re, os

def delete_page_cache(path):
	cache = frappe.cache()
	groups = ("website_page", "page_context")
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
		content, sender_full_name, creation, sender
		from `tabCommunication`
		where
			communication_type='Comment'
			and reference_doctype=%s
			and reference_name=%s
			and (comment_type is null or comment_type in ('Comment', 'Communication'))
			and modified >= DATE_SUB(NOW(),INTERVAL 1 YEAR)
		order by creation""", (doctype, name), as_dict=1) or []

def get_home_page():
	if frappe.local.flags.home_page:
		return frappe.local.flags.home_page

	def _get_home_page():
		home_page = None

		get_website_user_home_page = frappe.get_hooks('get_website_user_home_page')
		if get_website_user_home_page:
			home_page = frappe.get_attr(get_website_user_home_page[-1])(frappe.session.user)

		if not home_page:
			role_home_page = frappe.get_hooks("role_home_page")
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

		home_page = home_page.strip('/')

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

	return name[:140]


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

def get_full_index(route=None, app=None):
	"""Returns full index of the website for www upto the n-th level"""
	if not frappe.local.flags.children_map:
		from frappe.website.router import get_pages
		children_map = {}
		pages = get_pages(app=app)

		# make children map
		for route, page_info in pages.iteritems():
			parent_route = os.path.dirname(route)
			children_map.setdefault(parent_route, []).append(page_info)

			if frappe.flags.local_docs:
				page_info.extn = '.html'

		# order as per index if present
		for route, children in children_map.items():
			page_info = pages[route]
			if page_info.index:
				new_children = []
				page_info.extn = ''
				for name in page_info.index:
					child_route = page_info.route + '/' + name
					if child_route in pages:
						new_children.append(pages[child_route])

				# add remaining pages not in index.txt
				for c in children:
					if c not in new_children:
						new_children.append(c)

				children_map[route] = new_children

		frappe.local.flags.children_map = children_map

	return frappe.local.flags.children_map

def extract_title(source, path):
	'''Returns title from `&lt;!-- title --&gt;` or &lt;h1&gt; or path'''
	if "<!-- title:" in source:
		title = re.findall('<!-- title:([^>]*) -->', source)[0].strip()
	elif "<h1>" in source:
		match = re.findall('<h1>([^<]*)', source)
		title = match[0].strip()[:300]
	else:
		title = os.path.basename(path).replace('_', ' ').replace('-', ' ').title()

	return title
