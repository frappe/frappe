from __future__ import unicode_literals

import re, frappe

def resolve_redirect(path, query_string=None):
	'''
	Resolve redirects from hooks

	Example:

		website_redirect = [
			# absolute location
			{"source": "/from", "target": "https://mysite/from"},

			# relative location
			{"source": "/from", "target": "/main"},

			# use regex
			{"source": r"/from/(.*)", "target": r"/main/\1"}
			# use r as a string prefix if you use regex groups or want to escape any string literal
		]
	'''
	redirects = frappe.get_hooks('website_redirects')
	redirects += frappe.db.get_all('Website Route Redirect', ['source', 'target'])

	if not redirects: return

	redirect_to = frappe.cache().hget('website_redirects', path)

	if redirect_to:
		frappe.flags.redirect_location = redirect_to
		raise frappe.Redirect

	for rule in redirects:
		pattern = rule['source'].strip('/ ') + '$'
		path_to_match = path
		if rule.get('match_with_query_string'):
			path_to_match = path + '?' + frappe.safe_decode(query_string)

		if re.match(pattern, path_to_match):
			redirect_to = re.sub(pattern, rule['target'], path_to_match)
			frappe.flags.redirect_location = redirect_to
			frappe.cache().hset('website_redirects', path_to_match, redirect_to)
			raise frappe.Redirect

