# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, re

def scrub_relative_urls(html):
	"""prepend a slash before a relative url"""
	html = re.sub("""(src|href)[^\w'"]*['"](?!http|ftp|/|#|%|{)([^'" >]+)['"]""", '\g<1> = "/\g<2>"', html)
	html = re.sub("""url\((?!http|ftp|/|#|%|{)([^\(\)]+)\)""", 'url(/\g<1>)', html)
	return html

def find_first_image(html):
	m = re.finditer("""<img[^>]*src\s?=\s?['"]([^'"]*)['"]""", html)
	try:
		return m.next().groups()[0]
	except StopIteration:
		return None

def can_cache(no_cache=False):
	return not (frappe.conf.disable_website_cache or no_cache)

def get_home_page():
	home_page = frappe.cache().get_value("home_page", \
		lambda:  (frappe.get_hooks("home_page") \
			or [frappe.db.get_value("Website Settings", None, "home_page") \
			or "login"])[0])

	return home_page

def is_signup_enabled():
	if getattr(frappe.local, "is_signup_enabled", None) is None:
		frappe.local.is_signup_enabled = True
		if frappe.utils.cint(frappe.db.get_value("Website Settings",
			"Website Settings", "disable_signup")):
				frappe.local.is_signup_enabled = False

	return frappe.local.is_signup_enabled

def cleanup_page_name(title):
	"""make page name from title"""
	name = title.lower()
	name = re.sub('[~!@#$%^&*+()<>,."\'\?]', '', name)
	name = re.sub('[:/]', '-', name)

	name = '-'.join(name.split())

	# replace repeating hyphens
	name = re.sub(r"(-)\1+", r"\1", name)

	return name

def get_hex_shade(color, percent):
	def p(c):
		v = int(c, 16) + int(int('ff', 16) * (float(percent)/100))
		if v < 0:
			v=0
		if v > 255:
			v=255
		h = hex(v)[2:]
		if len(h) < 2:
			h = "0" + h
		return h

	r, g, b = color[0:2], color[2:4], color[4:6]

	avg = (float(int(r, 16) + int(g, 16) + int(b, 16)) / 3)
	# switch dark and light shades
	if avg > 128:
		percent = -percent

	# stronger diff for darker shades
	if percent < 25 and avg < 64:
		percent = percent * 2

	return p(r) + p(g) + p(b)
