from functools import lru_cache

import frappe
from frappe.tests.microbenchmarks.utils import NanoBenchmark


def bench_get_doc():
	return [frappe.get_doc("Role", r) for r in get_all_roles()]


def bench_get_user():
	"""Complex version of get_doc - involves child documents to init"""
	guest = frappe.get_doc("User", "Guest")
	admin = frappe.get_doc("User", "Administrator")
	return guest, admin


def bench_save_doc():
	# This doctype is used because it has nothing,
	# so we are essentially measuring typical "overheads"
	frappe.get_doc("Gender", "Other").save()


bench_new_doc = NanoBenchmark('frappe.new_doc("Role")')


def bench_get_cached_doc():
	docs = []
	for role in get_all_roles():
		doctype = "Role"

		docs.append(frappe.get_cached_doc(doctype, role))

	# Clear "local" cache to avoid testing basically nothing.
	frappe.local.cache.clear()
	return docs


def bench_get_meta():
	metas = []
	for doctype in get_doctypes():
		metas.append(frappe.get_meta(doctype))
	frappe.local.cache.clear()
	return metas


def bench_get_local_cached_doc():
	docs = []
	doctype = "Role"
	for role in get_all_roles():
		docs.append(frappe.get_cached_doc(doctype, role))
	return docs


bench_get_all = NanoBenchmark('frappe.get_all("DocField", "*", limit=1, run=0)')

bench_get_list = NanoBenchmark('frappe.get_list("Role", "*", limit=20, run=0)')


bench_get_all_with_filters = NanoBenchmark(
	'frappe.get_all("Role", {"creation": (">", "2020-01-01 00:00:00")}, "disabled", limit=10, run=0)'
)

bench_get_all_with_many_fields = NanoBenchmark(
	"""frappe.get_all(
		"Role",
		{"creation": (">", "2020-01-01 00:00:00")},
		["disabled", "name", "creation", "modified"],
		limit=10,
		run=0)"""
)


def bench_link_validation():
	user = frappe.get_cached_doc("User", "Administrator")
	user._action = "save"
	user._validate_links()
	frappe.db.value_cache.clear()  # Avoid reusing local validations


@lru_cache
def get_all_roles():
	return frappe.get_all("Role", order_by="creation asc", limit=10, pluck="name")


@lru_cache
def get_doctypes(limit=50):
	return frappe.get_all("DocType", order_by="creation asc", limit=limit, pluck="name")


bench_doc_to_dict = NanoBenchmark("doc.as_dict()", setup='doc=frappe.get_doc("User", "Guest")')
