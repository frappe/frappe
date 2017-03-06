from __future__ import unicode_literals
import frappe
from frappe.utils.global_search import web_search

def get_context(context):
	context.no_cache = 1
	context.update(get_search_results(frappe.form_dict.q))

@frappe.whitelist(allow_guest = True)
def get_search_results(text, start=0, as_html=False):
	results = web_search(text, start, limit=21)
	out = frappe._dict()

	if len(results) == 21:
		out.has_more = 1
		results = results[:20]

	for d in results:
		index = d.content.lower().index(text.lower())
		if index < 40:
			start = 0
			prefix = ''
		else:
			start = index - 40
			prefix = '...'

		suffix = ''
		if (index + len(text) + 40) < len(d.content):
			 suffix = '...'

		d.preview = prefix + d.content[start:start + len(text) + 80].replace(text, '<b>' + text + '</b>') + suffix

	out.results = results

	if as_html:
		out.results = frappe.render_template('templates/includes/search_result.html', out)

	return out