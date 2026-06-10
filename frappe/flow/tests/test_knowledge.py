# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.tests import IntegrationTestCase

from flow.knowledge import store

DIM = 4


def _rows():
	return [
		{
			"id": 1,
			"kb": "Helpdesk",
			"source": "SRC-a",
			"content": "wifi not connecting on macbook",
			"vector": [1.0, 0.0, 0.0, 0.0],
		},
		{
			"id": 2,
			"kb": "Helpdesk",
			"source": "SRC-a",
			"content": "printer not detected on windows",
			"vector": [0.0, 1.0, 0.0, 0.0],
		},
		{
			"id": 3,
			"kb": "Onboarding",
			"source": "SRC-b",
			"content": "how to set up your laptop",
			"vector": [0.9, 0.1, 0.0, 0.0],
		},
	]


class TestKnowledgeStore(IntegrationTestCase):
	def setUp(self):
		store.drop_table()

	def tearDown(self):
		store.drop_table()

	def _seed(self):
		store.ensure_table_for_dimension(DIM)
		store.add(_rows())

	def test_ensure_table_is_idempotent(self):
		store.ensure_table_for_dimension(DIM)
		store.ensure_table_for_dimension(DIM)
		self.assertTrue(store.table_exists())
		self.assertEqual(store.table_dimension(), DIM)

	def test_ensure_table_rejects_dimension_change(self):
		store.ensure_table_for_dimension(DIM)
		with self.assertRaisesRegex(frappe.ValidationError, "Rebuild"):
			store.ensure_table_for_dimension(DIM + 1)

	def test_ensure_table_rejects_invalid_dimension(self):
		with self.assertRaises(ValueError):
			store.ensure_table_for_dimension(0)

	def test_search_before_table_exists_returns_empty(self):
		self.assertEqual(store.search([1.0, 0.0, 0.0, 0.0]), [])

	def test_search_on_empty_table_returns_empty(self):
		store.ensure_table_for_dimension(DIM)
		self.assertEqual(store.search([1.0, 0.0, 0.0, 0.0]), [])

	def test_vector_search_ranks_by_similarity(self):
		self._seed()
		hits = store.search([1.0, 0.0, 0.0, 0.0], limit=2)
		self.assertEqual([h["id"] for h in hits], [1, 3])
		self.assertGreater(hits[0]["score"], hits[1]["score"])

	def test_search_scopes_to_knowledge_bases(self):
		self._seed()
		hits = store.search([1.0, 0.0, 0.0, 0.0], kbs=["Onboarding"], limit=5)
		self.assertEqual([h["kb"] for h in hits], ["Onboarding"])

	def test_hybrid_search_surfaces_keyword_match(self):
		self._seed()
		hits = store.search([0.0, 0.0, 1.0, 0.0], text="printer", limit=3)
		self.assertIn(2, [h["id"] for h in hits])

	def test_hybrid_search_finds_rows_added_after_index_creation(self):
		self._seed()
		store.add(
			[
				{
					"id": 4,
					"kb": "Helpdesk",
					"source": "SRC-c",
					"content": "vpn conflict after update",
					"vector": [0.0, 0.0, 1.0, 0.0],
				}
			]
		)
		hits = store.search([0.0, 0.0, 1.0, 0.0], text="vpn", limit=3)
		self.assertEqual(hits[0]["id"], 4)

	def test_delete_by_source(self):
		self._seed()
		store.delete(source="SRC-a")
		hits = store.search([1.0, 0.0, 0.0, 0.0], limit=5)
		self.assertEqual([h["id"] for h in hits], [3])

	def test_delete_by_ids(self):
		self._seed()
		store.delete(ids=[1, 3])
		hits = store.search([1.0, 0.0, 0.0, 0.0], limit=5)
		self.assertEqual([h["id"] for h in hits], [2])

	def test_delete_with_empty_ids_is_noop(self):
		self._seed()
		store.delete(ids=[])
		self.assertEqual(len(store.search([1.0, 0.0, 0.0, 0.0], limit=5)), 3)

	def test_delete_requires_a_criterion(self):
		with self.assertRaises(ValueError):
			store.delete()

	def test_filter_values_with_quotes_are_escaped(self):
		self._seed()
		hits = store.search([1.0, 0.0, 0.0, 0.0], kbs=["x'; DROP TABLE chunks; --"], limit=5)
		self.assertEqual(hits, [])
		self.assertTrue(store.table_exists())

	def test_add_requires_table(self):
		with self.assertRaisesRegex(frappe.ValidationError, "not initialized"):
			store.add(_rows())
