from functools import lru_cache

import frappe
from frappe.tests.microbenchmarks.bench_orm import get_all_roles
from frappe.tests.microbenchmarks.utils import NanoBenchmark

bench_make_key = NanoBenchmark("frappe.cache.make_key('a')")


def bench_redis_get_set_delete_cycle():
	for dt in get_all_doctypes():
		key = f"_test_set_value:{dt}"
		frappe.cache.set_value(key, cached_get_doc(dt), expires_in_sec=30)
		assert frappe.cache.exists(key)
		assert frappe.cache.get_value(key).name == dt
		frappe.cache.delete_value(key)
		assert not frappe.cache.exists(key)


def bench_redis_get_local_value():
	# After warmup all of these will be from local cache
	# test basically exercises local caching mechanisms
	docs = []
	doctype = "Role"
	for role in get_all_roles():
		docs.append(frappe.get_cached_doc(doctype, role))
	return docs


@lru_cache
def get_all_doctypes():
	return frappe.get_all("DocType", order_by="creation asc", limit=100, pluck="name")


@lru_cache
def cached_get_doc(doctype):
	return frappe.get_doc("DocType", doctype)
