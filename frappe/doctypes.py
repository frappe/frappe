from typing import Dict, Type
from frappe.model.document import Document
from frappe.model.base_document import get_controller

import frappe

FRAPPE_KEY = bytes("frappe", "utf8")


def modulize(dt: str) -> str:
	"""Convert string into importable Python namespace
	"""
	return dt.replace(" ", "").replace("-", "_")


def generate_doctype_map() -> Dict[str, Type[Document]]:
	"""Generate and return DocType -> Module Controller mapping
	"""
	doctype_mapping = {}
	modules = frappe.get_all("Module Def", {"app_name": "frappe"}, pluck="name")
	doctypes = frappe.get_all(
		"DocType", {"module": ("in", modules), "custom": False}, pluck="name"
	)

	for dt in doctypes:
		dt_ct = modulize(dt)
		try:
			doctype_mapping[dt_ct] = get_controller(dt)
		except ImportError:
			continue
	return doctype_mapping


def generate():
	"""Set bench_controllers cache in Redis
	"""
	if frappe.cache().hgetall("bench_controllers").get(FRAPPE_KEY):
		return

	frappe.cache().hget(
		"bench_controllers", "frappe", generator=generate_doctype_map, shared=True
	)


try:
	BENCH_CONTROLLERS = frappe.cache().hgetall("bench_controllers").get(FRAPPE_KEY, {}) or {}
except Exception:
	BENCH_CONTROLLERS = generate_doctype_map()


# loads controllers from Redis and save it under the frappe.doctypes namespace
for dt, ct in BENCH_CONTROLLERS.items():
	globals()[modulize(dt)] = ct
