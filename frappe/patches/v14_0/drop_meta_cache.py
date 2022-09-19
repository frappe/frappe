import frappe


def execute():
	cache = frappe.cache()
	for key in cache.hkeys("meta"):
		cache.hdel("meta", key)
