# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json
import os
import re

import redis

import frappe
from frappe.model.base_document import get_controller
from frappe.utils import cint, strip_html_tags
from frappe.utils.data import cstr
from frappe.utils.html_utils import unescape_html

HTML_TAGS_PATTERN = re.compile(r"(?s)<[\s]*(script|style).*?</\1>")


def setup_global_search_table():
	"""
	Creates __global_search table
	:return:
	"""
	frappe.db.create_global_search_table()


def reset():
	"""
	Deletes all data in __global_search
	:return:
	"""
	frappe.db.delete("__global_search")


def get_doctypes_with_global_search(with_child_tables=True):
	"""
	Return doctypes with global search fields
	:param with_child_tables:
	:return:
	"""

	def _get():
		global_search_doctypes = []
		filters = {}
		if not with_child_tables:
			filters = {"istable": ["!=", 1], "issingle": ["!=", 1]}
		for d in frappe.get_all("DocType", fields=["name", "module"], filters=filters):
			meta = frappe.get_meta(d.name)
			if len(meta.get_global_search_fields()) > 0:
				global_search_doctypes.append(d)

		installed_apps = frappe.get_installed_apps()
		module_app = frappe.local.module_app

		doctypes = [
			d.name
			for d in global_search_doctypes
			if module_app.get(frappe.scrub(d.module))
			and module_app[frappe.scrub(d.module)] in installed_apps
		]

		return doctypes

	return frappe.cache().get_value("doctypes_with_global_search", _get)


def rebuild_for_doctype(doctype):
	"""
	Rebuild entries of doctype's documents in __global_search on change of
	searchable fields
	:param doctype: Doctype
	"""
	if frappe.local.conf.get("disable_global_search"):
		return

	def _get_filters():
		filters = frappe._dict({"docstatus": ["!=", 2]})
		if meta.has_field("enabled"):
			filters.enabled = 1
		if meta.has_field("disabled"):
			filters.disabled = 0

		return filters

	meta = frappe.get_meta(doctype)

	if cint(meta.issingle) == 1:
		return

	if cint(meta.istable) == 1:
		parent_doctypes = frappe.get_all(
			"DocField",
			fields="parent",
			filters={"fieldtype": ["in", frappe.model.table_fields], "options": doctype},
		)
		for p in parent_doctypes:
			rebuild_for_doctype(p.parent)

		return

	# Delete records
	delete_global_search_records_for_doctype(doctype)

	parent_search_fields = meta.get_global_search_fields()
	fieldnames = get_selected_fields(meta, parent_search_fields)

	# Get all records from parent doctype table
	all_records = frappe.get_all(doctype, fields=fieldnames, filters=_get_filters())

	# Children data
	all_children, child_search_fields = get_children_data(doctype, meta)
	all_contents = []

	for doc in all_records:
		content = []
		for field in parent_search_fields:
			value = doc.get(field.fieldname)
			if value:
				content.append(get_formatted_value(value, field))

		# get children data
		for child_doctype, records in all_children.get(doc.name, {}).items():
			for field in child_search_fields.get(child_doctype):
				for r in records:
					if r.get(field.fieldname):
						content.append(get_formatted_value(r.get(field.fieldname), field))

		if content:
			# if doctype published in website, push title, route etc.
			published = 0
			title, route = "", ""
			try:
				if hasattr(get_controller(doctype), "is_website_published") and meta.allow_guest_to_view:
					d = frappe.get_doc(doctype, doc.name)
					published = 1 if d.is_website_published() else 0
					title = d.get_title()
					route = d.get("route")
			except ImportError:
				# some doctypes has been deleted via future patch, hence controller does not exists
				pass

			all_contents.append(
				{
					"doctype": frappe.db.escape(doctype),
					"name": frappe.db.escape(doc.name),
					"content": frappe.db.escape(" ||| ".join(content or "")),
					"published": published,
					"title": frappe.db.escape((title or "")[: int(frappe.db.VARCHAR_LEN)]),
					"route": frappe.db.escape((route or "")[: int(frappe.db.VARCHAR_LEN)]),
				}
			)
	if all_contents:
		insert_values_for_multiple_docs(all_contents)


def delete_global_search_records_for_doctype(doctype):
	frappe.db.delete("__global_search", {"doctype": doctype})


def get_selected_fields(meta, global_search_fields):
	fieldnames = [df.fieldname for df in global_search_fields]
	if meta.istable == 1:
		fieldnames.append("parent")
	elif "name" not in fieldnames:
		fieldnames.append("name")

	if meta.has_field("is_website_published"):
		fieldnames.append("is_website_published")

	return fieldnames


def get_children_data(doctype, meta):
	"""
	Get all records from all the child tables of a doctype

	all_children = {
	        "parent1": {
	                "child_doctype1": [
	                        {
	                                "field1": val1,
	                                "field2": val2
	                        }
	                ]
	        }
	}

	"""
	all_children = frappe._dict()
	child_search_fields = frappe._dict()

	for child in meta.get_table_fields():
		child_meta = frappe.get_meta(child.options)
		search_fields = child_meta.get_global_search_fields()
		if search_fields:
			child_search_fields.setdefault(child.options, search_fields)
			child_fieldnames = get_selected_fields(child_meta, search_fields)
			child_records = frappe.get_all(
				child.options, fields=child_fieldnames, filters={"docstatus": ["!=", 1], "parenttype": doctype}
			)

			for record in child_records:
				all_children.setdefault(record.parent, frappe._dict()).setdefault(child.options, []).append(
					record
				)

	return all_children, child_search_fields


def insert_values_for_multiple_docs(all_contents):
	values = []
	for content in all_contents:
		values.append("({doctype}, {name}, {content}, {published}, {title}, {route})".format(**content))

	batch_size = 50000
	for i in range(0, len(values), batch_size):
		batch_values = values[i : i + batch_size]
		# ignoring duplicate keys for doctype_name
		frappe.db.multisql(
			{
				"mariadb": """INSERT IGNORE INTO `__global_search`
				(doctype, name, content, published, title, route)
				VALUES {} """.format(
					", ".join(batch_values)
				),
				"postgres": """INSERT INTO `__global_search`
				(doctype, name, content, published, title, route)
				VALUES {}
				ON CONFLICT("name", "doctype") DO NOTHING""".format(
					", ".join(batch_values)
				),
			}
		)


def update_global_search(doc):
	"""
	Add values marked with `in_global_search` to
	`global_search_queue` from given doc
	:param doc: Document to be added to global search
	"""
	if frappe.local.conf.get("disable_global_search"):
		return

	if (
		doc.docstatus > 1
		or (doc.meta.has_field("enabled") and not doc.get("enabled"))
		or doc.get("disabled")
	):
		return

	content = []
	for field in doc.meta.get_global_search_fields():
		if doc.get(field.fieldname) and field.fieldtype not in frappe.model.table_fields:
			content.append(get_formatted_value(doc.get(field.fieldname), field))

	# Get children
	for child in doc.meta.get_table_fields():
		for d in doc.get(child.fieldname):
			if d.parent == doc.name:
				for field in d.meta.get_global_search_fields():
					if d.get(field.fieldname):
						content.append(get_formatted_value(d.get(field.fieldname), field))

	if content:
		published = 0
		if hasattr(doc, "is_website_published") and doc.meta.allow_guest_to_view:
			published = 1 if doc.is_website_published() else 0

		title = (cstr(doc.get_title()) or "")[: int(frappe.db.VARCHAR_LEN)]
		route = doc.get("route") if doc else ""

		value = dict(
			doctype=doc.doctype,
			name=doc.name,
			content=" ||| ".join(content or ""),
			published=published,
			title=title,
			route=route,
		)

		sync_value_in_queue(value)


def update_global_search_for_all_web_pages():
	if frappe.conf.get("disable_global_search"):
		return

	print("Update global search for all web pages...")
	routes_to_index = get_routes_to_index()
	for route in routes_to_index:
		add_route_to_global_search(route)
	sync_global_search()


def get_routes_to_index():
	apps = frappe.get_installed_apps()

	routes_to_index = []
	for app in apps:
		base = frappe.get_app_path(app, "www")
		path_to_index = frappe.get_app_path(app, "www")

		for dirpath, _, filenames in os.walk(path_to_index, topdown=True):
			for f in filenames:
				if f.endswith((".md", ".html")):
					filepath = os.path.join(dirpath, f)

					route = os.path.relpath(filepath, base)
					route = route.split(".", 1)[0]

					if route.endswith("index"):
						route = route.rsplit("index", 1)[0]

					routes_to_index.append(route)

	return routes_to_index


def add_route_to_global_search(route):
	from bs4 import BeautifulSoup

	from frappe.utils import set_request
	from frappe.website.serve import get_response_content

	frappe.set_user("Guest")
	frappe.local.no_cache = True

	try:
		set_request(method="GET", path=route)
		content = get_response_content(route)
		soup = BeautifulSoup(content, "html.parser")
		page_content = soup.find(class_="page_content")
		text_content = page_content.text if page_content else ""
		title = soup.title.text.strip() if soup.title else route

		value = dict(
			doctype="Static Web Page",
			name=route,
			content=text_content,
			published=1,
			title=title,
			route=route,
		)
		sync_value_in_queue(value)
	except Exception:
		pass

	frappe.set_user("Administrator")


def get_formatted_value(value, field):
	"""
	Prepare field from raw data
	:param value:
	:param field:
	:return:
	"""

	if getattr(field, "fieldtype", None) in ["Text", "Text Editor"]:
		value = unescape_html(frappe.safe_decode(value))
		value = HTML_TAGS_PATTERN.subn("", str(value))[0]
		value = " ".join(value.split())
	return field.label + " : " + strip_html_tags(str(value))


def sync_global_search():
	"""
	Inserts / updates values from `global_search_queue` to __global_search.
	This is called via job scheduler
	:param flags:
	:return:
	"""
	while frappe.cache().llen("global_search_queue") > 0:
		# rpop to follow FIFO
		# Last one should override all previous contents of same document
		value = json.loads(frappe.cache().rpop("global_search_queue").decode("utf-8"))
		sync_value(value)


def sync_value_in_queue(value):
	try:
		# append to search queue if connected
		frappe.cache().lpush("global_search_queue", json.dumps(value))
	except redis.exceptions.ConnectionError:
		# not connected, sync directly
		sync_value(value)


def sync_value(value):
	"""
	Sync a given document to global search
	:param value: dict of { doctype, name, content, published, title, route }
	"""

	frappe.db.multisql(
		{
			"mariadb": """INSERT INTO `__global_search`
			(`doctype`, `name`, `content`, `published`, `title`, `route`)
			VALUES (%(doctype)s, %(name)s, %(content)s, %(published)s, %(title)s, %(route)s)
			ON DUPLICATE key UPDATE
				`content`=%(content)s,
				`published`=%(published)s,
				`title`=%(title)s,
				`route`=%(route)s
		""",
			"postgres": """INSERT INTO `__global_search`
			(`doctype`, `name`, `content`, `published`, `title`, `route`)
			VALUES (%(doctype)s, %(name)s, %(content)s, %(published)s, %(title)s, %(route)s)
			ON CONFLICT("doctype", "name") DO UPDATE SET
				`content`=%(content)s,
				`published`=%(published)s,
				`title`=%(title)s,
				`route`=%(route)s
		""",
		},
		value,
	)


def delete_for_document(doc):
	"""
	Delete the __global_search entry of a document that has
	been deleted
	:param doc: Deleted document
	"""
	frappe.db.delete("__global_search", {"doctype": doc.doctype, "name": doc.name})


@frappe.whitelist()
def search(text, start=0, limit=20, doctype=""):
	"""
	Search for given text in __global_search
	:param text: phrase to be searched
	:param start: start results at, default 0
	:param limit: number of results to return, default 20
	:return: Array of result objects
	"""
	from frappe.desk.doctype.global_search_settings.global_search_settings import (
		get_doctypes_for_global_search,
	)
	from frappe.query_builder.functions import Match

	results = []
	sorted_results = []

	allowed_doctypes = set(get_doctypes_for_global_search()) & set(frappe.get_user().get_can_read())
	if not allowed_doctypes or (doctype and doctype not in allowed_doctypes):
		return []

	for word in set(text.split("&")):
		word = word.strip()
		if not word:
			continue

		global_search = frappe.qb.Table("__global_search")
		rank = Match(global_search.content).Against(word).as_("rank")
		query = (
			frappe.qb.from_(global_search)
			.select(global_search.doctype, global_search.name, global_search.content, rank)
			.orderby("rank", order=frappe.qb.desc)
			.limit(limit)
		)

		if doctype:
			query = query.where(global_search.doctype == doctype)
		else:
			query = query.where(global_search.doctype.isin(allowed_doctypes))

		if cint(start) > 0:
			query = query.offset(start)

		result = query.run(as_dict=True)

		results.extend(result)

	# sort results based on allowed_doctype's priority
	for doctype in allowed_doctypes:
		for index, r in enumerate(results):
			if r.doctype == doctype and r.rank > 0.0:
				try:
					meta = frappe.get_meta(r.doctype)
					if meta.image_field:
						r.image = frappe.db.get_value(r.doctype, r.name, meta.image_field)
				except Exception:
					frappe.clear_messages()

				sorted_results.extend([r])

	return sorted_results


@frappe.whitelist(allow_guest=True)
def web_search(text, scope=None, start=0, limit=20):
	"""
	Search for given text in __global_search where published = 1
	:param text: phrase to be searched
	:param scope: search only in this route, for e.g /docs
	:param start: start results at, default 0
	:param limit: number of results to return, default 20
	:return: Array of result objects
	"""

	results = []
	texts = text.split("&")
	for text in texts:
		common_query = """ SELECT `doctype`, `name`, `content`, `title`, `route`
			FROM `__global_search`
			WHERE {conditions}
			LIMIT %(limit)s OFFSET %(start)s"""

		scope_condition = "`route` like %(scope)s AND " if scope else ""
		published_condition = "`published` = 1 AND "
		mariadb_conditions = postgres_conditions = " ".join([published_condition, scope_condition])

		# https://mariadb.com/kb/en/library/full-text-index-overview/#in-boolean-mode
		mariadb_conditions += "MATCH(`content`) AGAINST ({} IN BOOLEAN MODE)".format(
			frappe.db.escape("+" + text + "*")
		)
		postgres_conditions += 'TO_TSVECTOR("content") @@ PLAINTO_TSQUERY({})'.format(
			frappe.db.escape(text)
		)

		values = {"scope": "".join([scope, "%"]) if scope else "", "limit": limit, "start": start}

		result = frappe.db.multisql(
			{
				"mariadb": common_query.format(conditions=mariadb_conditions),
				"postgres": common_query.format(conditions=postgres_conditions),
			},
			values=values,
			as_dict=True,
		)
		tmp_result = []
		for i in result:
			if i in results or not results:
				tmp_result.append(i)
		results += tmp_result

	# chart of accounts -> {chart, of, accounts}
	# titles that match the most of these words will have high relevance
	words = set(get_distinct_words(text))
	for r in results:
		title_words = set(get_distinct_words(r.title))
		words_match = len(words.intersection(title_words))
		r.relevance = words_match

	results = sorted(results, key=lambda x: x.relevance, reverse=True)
	return results


def get_distinct_words(text):
	text = text.replace('"', "")
	text = text.replace("'", "")
	return [w.strip().lower() for w in text.split(" ")]
