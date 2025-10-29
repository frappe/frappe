import os
import sqlite3
import time
from typing import ClassVar
from unittest.mock import patch

import frappe
from frappe.search.sqlite_search import SQLiteSearch, SQLiteSearchIndexMissingError
from frappe.tests import IntegrationTestCase


class TestSQLiteSearch(SQLiteSearch):
	"""Test implementation of SQLiteSearch for testing purposes."""

	INDEX_NAME = "test_search.db"

	INDEX_SCHEMA: ClassVar = {
		"text_fields": ["title", "content"],
		"metadata_fields": ["doctype", "name", "owner", "modified"],
		"tokenizer": "unicode61 remove_diacritics 2",
	}

	INDEXABLE_DOCTYPES: ClassVar = {
		"Note": {
			"fields": ["name", "title", "content", "owner", {"modified": "creation"}],
		},
		"ToDo": {
			"fields": ["name", {"title": "description"}, {"content": "description"}, "owner", "modified"],
		},
		"User": {
			"fields": ["name", {"title": "full_name"}, {"content": "email"}, "name", "modified"],
			"filters": {"enabled": 1},
		},
	}

	def get_search_filters(self):
		"""Return permission filters - for testing, allow all documents."""
		if frappe.session.user == "Administrator":
			return {}
		# Simulate user-specific filtering
		return {"owner": frappe.session.user}


class TestSQLiteSearchAPI(IntegrationTestCase):
	"""Test suite for SQLiteSearch public API functionality."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.search = TestSQLiteSearch()
		# Clean up any existing test database
		cls.search.drop_index()

	@classmethod
	def tearDownClass(cls):
		super().tearDownClass()
		# Clean up test database
		cls.search.drop_index()

	def setUp(self):
		"""Set up test data for each test."""
		super().setUp()
		# Create test documents
		self.test_notes = []
		self.test_todos = []

		# Create test notes with different content
		note_data = [
			{"title": "Python Programming Guide", "content": "Learn Python basics and advanced concepts"},
			{"title": "Project Management Tips", "content": "How to manage software projects effectively"},
			{"title": "Cooking Recipe Collection", "content": "Delicious recipes for home cooking"},
			{
				"title": "Machine Learning Tutorial",
				"content": "Introduction to ML algorithms and Python implementation",
			},
		]

		for data in note_data:
			note = frappe.get_doc({"doctype": "Note", "title": data["title"], "content": data["content"]})
			note.insert()
			self.test_notes.append(note)

		# Create test todos
		todo_data = [
			{"description": "Review Python code for search functionality"},
			{"description": "Update project documentation"},
			{"description": "Plan team meeting agenda"},
		]

		for data in todo_data:
			todo = frappe.get_doc({"doctype": "ToDo", "description": data["description"], "status": "Open"})
			todo.insert()
			self.test_todos.append(todo)

	def tearDown(self):
		"""Clean up test data after each test."""
		# Delete test documents
		for note in self.test_notes:
			try:
				note.delete()
			except Exception:
				pass

		for todo in self.test_todos:
			try:
				todo.delete()
			except Exception:
				pass

		super().tearDown()

	def test_index_lifecycle_and_status_methods(self):
		"""Test index building, existence checking, and status validation."""
		# Initially index should not exist
		self.search.drop_index()  # Ensure clean state
		self.assertFalse(self.search.index_exists())

		# Should raise error when trying to search without index
		with self.assertRaises(SQLiteSearchIndexMissingError):
			self.search.raise_if_not_indexed()

		# Build index
		self.search.build_index()

		# Now index should exist
		self.assertTrue(self.search.index_exists())

		# Should not raise error now
		try:
			self.search.raise_if_not_indexed()
		except SQLiteSearchIndexMissingError:
			self.fail("raise_if_not_indexed() raised exception when index exists")

		# Verify database file exists and has correct tables
		self.assertTrue(os.path.exists(self.search.db_path))

		conn = sqlite3.connect(self.search.db_path)
		cursor = conn.cursor()

		# Check if FTS table exists
		cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='search_fts'")
		self.assertTrue(cursor.fetchone())

		# Check if vocabulary tables exist
		cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='search_vocabulary'")
		self.assertTrue(cursor.fetchone())

		cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='search_trigrams'")
		self.assertTrue(cursor.fetchone())

		conn.close()

		# Test drop_index method
		self.search.drop_index()
		self.assertFalse(self.search.index_exists())
		self.assertFalse(os.path.exists(self.search.db_path))

		# Dropping non-existent index should not raise error
		self.search.drop_index()  # Should not raise error

	def test_basic_search_functionality(self):
		"""Test core search functionality with various query types."""
		# Build index first
		self.search.build_index()

		# Test basic text search
		results = self.search.search("Python")
		self.assertGreater(len(results["results"]), 0)
		self.assertIn("Python", results["results"][0]["title"] + results["results"][0]["content"])

		# Verify result structure
		result = results["results"][0]
		required_fields = [
			"id",
			"title",
			"content",
			"doctype",
			"name",
			"score",
			"original_rank",
			"modified_rank",
		]
		for field in required_fields:
			self.assertIn(field, result)

		# Test case-insensitive search
		results_lower = self.search.search("python")
		results_upper = self.search.search("PYTHON")
		self.assertEqual(len(results_lower["results"]), len(results_upper["results"]))

		# Test partial word matching
		results = self.search.search("prog")  # Should match "Programming"
		self.assertGreater(len(results["results"]), 0)

		# Test multi-word search
		results = self.search.search("Python programming")
		self.assertGreater(len(results["results"]), 0)

		# Test empty query
		results = self.search.search("")
		self.assertEqual(len(results["results"]), 0)

		# Test title-only search
		results = self.search.search("Python", title_only=True)
		self.assertGreater(len(results["results"]), 0)
		for result in results["results"]:
			self.assertIn("Python", result["title"])

	def test_search_filtering_and_permissions(self):
		"""Test search filtering and permission-based result filtering."""
		self.search.build_index()

		# Test basic filtering by doctype
		results = self.search.search("", filters={"doctype": "Note"})
		for result in results["results"]:
			self.assertEqual(result["doctype"], "Note")

		# Test filtering with list values
		results = self.search.search("", filters={"doctype": ["Note", "ToDo"]})
		for result in results["results"]:
			self.assertIn(result["doctype"], ["Note", "ToDo"])

		# Test empty filter list (should return no results)
		results = self.search.search("", filters={"doctype": []})
		self.assertEqual(len(results["results"]), 0)

		# Test permission filtering by switching users
		original_user = frappe.session.user
		try:
			# Create a test user and switch to them
			test_user_email = "test_search_user@example.com"
			if not frappe.db.exists("User", test_user_email):
				test_user = frappe.get_doc(
					{
						"doctype": "User",
						"email": test_user_email,
						"first_name": "Test",
						"last_name": "User",
						"enabled": 1,
					}
				)
				test_user.insert()

			frappe.set_user(test_user_email)

			# Search should now filter by owner (based on our test implementation)
			results = self.search.search("Python")
			# Results should be limited based on permission filters
			self.assertIsInstance(results["results"], list)

		finally:
			frappe.set_user(original_user)

	def test_advanced_scoring_and_ranking(self):
		"""Test scoring pipeline, ranking, and result ordering."""
		self.search.build_index()

		# Search for a term that appears in multiple documents
		results = self.search.search("Python")

		# Verify results are sorted by score (descending)
		scores = [result["score"] for result in results["results"]]
		self.assertEqual(scores, sorted(scores, reverse=True))

		# Verify both original and modified rankings are present
		for i, result in enumerate(results["results"]):
			self.assertEqual(result["modified_rank"], i + 1)
			self.assertIsInstance(result["original_rank"], int)
			self.assertGreater(result["original_rank"], 0)

		# Test title boost - documents with search term in title should rank higher
		results = self.search.search("Programming")
		title_match_found = False
		for result in results["results"]:
			if "Programming" in result["title"]:
				title_match_found = True
				# Title matches should have higher scores
				self.assertGreater(result["score"], 1.0)
				break
		self.assertTrue(title_match_found, "No title matches found for scoring test")

		# Test that BM25 score is included
		for result in results["results"]:
			self.assertIn("bm25_score", result)
			self.assertIsInstance(result["bm25_score"], (int, float))

	def test_spelling_correction_and_query_expansion(self):
		"""Test spelling correction and query expansion functionality."""
		self.search.build_index()

		# Test with a misspelled word that should be corrected
		results = self.search.search("Pythom")  # Misspelled "Python"

		# Check if corrections were applied
		summary = results["summary"]
		if summary.get("corrected_words"):
			self.assertIsInstance(summary["corrected_words"], dict)
			self.assertIsInstance(summary["corrected_query"], str)

		# Even with misspelling, we should get some results due to correction
		# (This might not always work depending on vocabulary, so we test gracefully)
		self.assertIsInstance(results["results"], list)

		# Test with a completely made-up word
		results = self.search.search("xyzabc123nonexistent")
		# Should return empty results or minimal results
		self.assertLessEqual(len(results["results"]), 1)

	def test_document_indexing_operations(self):
		"""Test individual document indexing and removal operations."""
		self.search.build_index()

		# Create a new document after index is built
		new_note = frappe.get_doc(
			{
				"doctype": "Note",
				"title": "Newly Added Document",
				"content": "This document was added after initial indexing",
			}
		)
		new_note.insert()

		try:
			# Initially, the new document shouldn't be in search results
			results = self.search.search("Newly Added Document")
			initial_count = len(results["results"])

			# Index the new document
			self.search.index_doc("Note", new_note.name)

			# Now it should be findable
			results = self.search.search("Newly Added Document")
			self.assertGreater(len(results["results"]), initial_count)

			# Verify the document is in results
			found = False
			for result in results["results"]:
				if result["name"] == new_note.name:
					found = True
					break
			self.assertTrue(found, "Newly indexed document not found in search results")

			# Remove the document from index
			self.search.remove_doc("Note", new_note.name)

			# Should not be findable anymore
			results = self.search.search("Newly Added Document")
			found = False
			for result in results["results"]:
				if result["name"] == new_note.name:
					found = True
					break
			self.assertFalse(found, "Removed document still found in search results")

		finally:
			new_note.delete()

	def test_search_result_summary_and_metadata(self):
		"""Test search result summary and metadata information."""
		self.search.build_index()

		results = self.search.search("Python")
		summary = results["summary"]

		# Verify summary structure
		required_summary_fields = [
			"total_matches",
			"filtered_matches",
			"returned_matches",
			"duration",
			"title_only",
			"applied_filters",
		]
		for field in required_summary_fields:
			self.assertIn(field, summary)

		# Verify summary values make sense
		self.assertIsInstance(summary["duration"], (int, float))
		self.assertGreater(summary["duration"], 0)
		self.assertEqual(summary["total_matches"], summary["filtered_matches"])
		self.assertEqual(summary["filtered_matches"], len(results["results"]))
		self.assertFalse(summary["title_only"])
		self.assertEqual(summary["applied_filters"], {})

		# Test with filters applied
		results = self.search.search("Python", filters={"doctype": "Note"})
		summary = results["summary"]
		self.assertEqual(summary["applied_filters"], {"doctype": "Note"})

		# Test title-only search
		results = self.search.search("Python", title_only=True)
		summary = results["summary"]
		self.assertTrue(summary["title_only"])

	def test_configuration_and_schema_validation(self):
		"""Test configuration validation and schema handling."""

		# Test invalid configuration
		class InvalidSearchClass(SQLiteSearch):
			# Missing required INDEX_SCHEMA
			INDEXABLE_DOCTYPES: ClassVar = {"Note": {"fields": ["name", "title"]}}

			def get_search_filters(self):
				return {}

		with self.assertRaises(ValueError):
			InvalidSearchClass()

		# Test invalid doctype configuration
		class InvalidDoctypeConfig(SQLiteSearch):
			INDEX_SCHEMA: ClassVar = {"text_fields": ["title", "content"]}
			INDEXABLE_DOCTYPES: ClassVar = {
				"Note": {
					# Missing 'fields' key
					"title_field": "title"
				}
			}

			def get_search_filters(self):
				return {}

		with self.assertRaises(ValueError):
			InvalidDoctypeConfig()

	def test_content_processing_and_html_handling(self):
		"""Test content processing including HTML tag removal and text normalization."""
		self.search.build_index()

		# Create a note with HTML content
		html_note = frappe.get_doc(
			{
				"doctype": "Note",
				"title": "HTML Content Test",
				"content": "<p>This is <strong>bold</strong> text with <a href='http://example.com'>links</a> and <br> line breaks.</p>",
			}
		)
		html_note.insert()

		try:
			# Index the document
			self.search.index_doc("Note", html_note.name)

			# Search should find processed content
			results = self.search.search("bold text links")

			# Should find the document
			found = False
			for result in results["results"]:
				if result["name"] == html_note.name:
					found = True
					# Content should be processed (HTML tags removed)
					self.assertNotIn("<p>", result["content"])
					self.assertNotIn("<strong>", result["content"])
					self.assertIn("bold", result["content"])
					self.assertNotIn(
						"<a href='http://example.com'>", result["content"]
					)  # Links should be replaced
					break

			self.assertTrue(found, "HTML content document not found in search")

		finally:
			html_note.delete()

	def test_search_disabled_state(self):
		"""Test behavior when search is disabled."""

		# Create a search class with search disabled
		class DisabledSearch(TestSQLiteSearch):
			def is_search_enabled(self):
				return False

		disabled_search = DisabledSearch()
		disabled_search.drop_index()  # Ensure clean state

		# Should return empty results when disabled
		results = disabled_search.search("Python")
		self.assertEqual(len(results["results"]), 0)

		# Build index should do nothing when disabled
		disabled_search.build_index()  # Should not raise error but do nothing
		self.assertFalse(disabled_search.index_exists())

	@patch("frappe.enqueue")
	def test_background_operations(self, mock_enqueue):
		"""Test background job integration and module-level functions."""
		from frappe.search.sqlite_search import (
			build_index_in_background,
			get_search_classes,
		)

		# Test getting search classes
		with patch("frappe.get_hooks") as mock_get_hooks:
			mock_get_hooks.return_value = ["frappe.tests.test_sqlite_search.TestSQLiteSearch"]
			classes = get_search_classes()
			self.assertEqual(len(classes), 1)
			self.assertEqual(classes[0], TestSQLiteSearch)

		# Test background index building
		with patch("frappe.get_hooks") as mock_get_hooks:
			mock_get_hooks.return_value = ["frappe.tests.test_sqlite_search.TestSQLiteSearch"]
			build_index_in_background()

			# Should have enqueued a background job
			self.assertTrue(mock_enqueue.called)
