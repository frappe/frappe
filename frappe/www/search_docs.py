from __future__ import unicode_literals
import frappe
from frappe import _
from jinja2 import utils
from html2text import html2text
from frappe.utils import sanitize_html
from frappe.utils.help import get_installed_app_help

def get_context(context):
	context.no_cache = 1
	if frappe.form_dict.q:
		query = str(utils.escape(sanitize_html(frappe.form_dict.q)))
		context.title = _('Documentation Results for "{0}"').format(query)
		context.route = '/search_docs'
		d = frappe._dict()
		d.results = get_docs_results(query)
		context.update(d)
	else:
		context.title = _('Docs Search')

@frappe.whitelist(allow_guest = True)
def get_docs_results(text):
	out = []
	results = get_installed_app_help(text)
	for d in results:
		full_path = d[2]
		out.append(frappe._dict({
			'title': d[0],
			'preview': html2text(d[1]),
			'route': full_path[full_path.index('docs/'):]
		}))

	return out
