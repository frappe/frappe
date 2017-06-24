from __future__ import unicode_literals
import frappe
from frappe.utils.global_search import web_search
from html2text import html2text
from frappe import _

def get_context(context):
	context.no_cache = 1
	if frappe.form_dict.q:
		context.title = _('Search Results for "{0}"').format(frappe.form_dict.q)
		context.update(get_search_results(frappe.form_dict.q))
	else:
		context.title = _('Search')

@frappe.whitelist(allow_guest = True)
def get_search_results(text, start=0, as_html=False):
	results = web_search(text, start, limit=21)
	out = frappe._dict()

	if len(results) == 21:
		out.has_more = 1
		results = results[:20]

	for d in results:
		d.content = html2text(d.content)
		index = d.content.lower().index(text.lower())
		d.content = d.content[:index] + '<b>' + d.content[index:][:len(text)] + '</b>' + d.content[index + len(text):]

		if index < 40:
			start = 0
			prefix = ''
		else:
			start = index - 40
			prefix = '...'

		suffix = ''
		if (index + len(text) + 47) < len(d.content):
			 suffix = '...'

		d.preview = prefix + d.content[start:start + len(text) + 87] + suffix

	out.results = results

	if as_html:
		out.results = frappe.render_template('templates/includes/search_result.html', out)

	return out
