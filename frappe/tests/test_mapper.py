# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from frappe.tests import IntegrationTestCase
from frappe.tests.utils import whitelist_for_tests


@whitelist_for_tests()
def _collect_sources(source_name: str, target_doc: dict | None = None, args: dict | None = None):
	"""A minimal mapper method: accumulates source names (and optional args) onto the target."""
	target_doc = target_doc or {"sources": [], "args": None}
	target_doc["sources"].append(source_name)
	if args:
		target_doc["args"] = args
	return target_doc


class TestMapper(IntegrationTestCase):
	def test_map_docs_accepts_native_lists(self):
		from frappe.model.mapper import map_docs

		method = "frappe.tests.test_mapper._collect_sources"
		# source_names as a native list and args as a native dict (frappe.parse_json passthrough)
		target = map_docs(
			method=method,
			source_names=["SRC-001", "SRC-002"],
			target_doc={"sources": [], "args": None},
			args={"key": "val"},
		)
		self.assertEqual(target["sources"], ["SRC-001", "SRC-002"])
		self.assertEqual(target["args"], {"key": "val"})
