# -*- coding: utf-8 -*-

from __future__ import unicode_literals

docs_version = "7.x.x"

source_link = "https://github.com/frappe/frappe"
docs_base_url = "https://frappe.github.io/frappe"
headline = "Superhero Web Framework"
sub_heading = "Build extensions to ERPNext or make your own app"
hide_install = True
long_description = """Frappe is a full stack web application framework written in Python,
Javascript, HTML/CSS with MySQL as the backend. It was built for ERPNext
but is pretty generic and can be used to build database driven apps.

The key differece in Frappe compared to other frameworks is that Frappe
is that meta-data is also treated as data and is used to build front-ends
very easily. Frappe comes with a full blown admin UI called the **Desk**
that handles forms, navigation, lists, menus, permissions, file attachment
and much more out of the box.

Frappe also has a plug-in architecture that can be used to build plugins
to ERPNext.

Frappe Framework was designed to build [ERPNext](https://erpnext.com), open source
ERP for managing small and medium sized businesses.

[Get started with the Tutorial](https://frappe.github.io/frappe/user/)
"""
google_analytics_id = 'UA-8911157-23'

def get_context(context):
	context.brand_html = ('<img class="brand-logo" src="'+context.docs_base_url
		+'/assets/img/frappe-bird-white.png"> Frappé Framework</img>')
	context.top_bar_items = [
		{"label": "Tutorials", "url": context.docs_base_url + "/user", "right": 1},
		{"label": "API", "url": context.docs_base_url + "/current", "right": 1},
		{"label": "Forum", "url": 'https://discuss.erpnext.com', "right": 1}
	]
