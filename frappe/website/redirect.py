from __future__ import unicode_literals

import re, frappe

def resolve_redirect(path):
	'''
	Resolve redirects from hooks

	Example:

		website_redirect = [
			# absolute location
			{"source": "/from", "target": "https://mysite/from"},

			# relative location
			{"source": "/from", "target": "/main"},

			# use regex
			{"source": "/from/(.*)", "target": "/main/\1"}
		]
	'''
	redirects = frappe.get_hooks('website_redirects')
	if not redirects: return

	redirect_to = frappe.cache().hget('website_redirects', path)

	if redirect_to:
		frappe.flags.redirect_location = redirect_to
		raise frappe.Redirect

	for rule in redirects:
		pattern = rule['source'].strip('/ ') + '$'
		if re.match(pattern, path):
			redirect_to = re.sub(pattern, rule['target'].replace('\\', '\\\\'), path)
			frappe.flags.redirect_location = redirect_to
			frappe.cache().hset('website_redirects', path, redirect_to)
			raise frappe.Redirect

