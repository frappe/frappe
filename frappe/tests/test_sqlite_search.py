# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
import os
import tempfile
import time
from typing import ClassVar
from unittest.mock import Mock, patch

import frappe
from frappe.search.sqlite_search import (
	IndexWarning,
	SQLiteFTS5IndexMissingError,
	SQLiteSearch,
	WarningType,
)
from frappe.tests import IntegrationTestCase


class TestSQLiteSearch(SQLiteSearch):
	"""Test implementation of FrappeSQLiteSearch for testing purposes using new API."""

	INDEX_NAME = "test_search.db"

	INDEX_SCHEMA: ClassVar = {
		"metadata_fields": ["owner", "status"],
		"tokenizer": "unicode61 remove_diacritics 2",
	}

	INDEXABLE_DOCTYPES: ClassVar = {
		"Note": {
			"fields": ["name", "title", "content", "modified", "owner"],
			"filters": {},
		},
		"ToDo": {
			"fields": ["name", "title", {"content": "description"}, "status", "modified", "owner"],
			"filters": {"status": ("!=", "Deleted")},
		},
	}

	def __init__(self, db_name=None):
		self.test_docs = []
		super().__init__(db_name)

	def get_search_filters(self):
		# Simple test permission - only return docs owned by current user
		current_user = getattr(frappe, "session", {}).get("user", "Administrator")
		if current_user == "Administrator":
			return {}
		return {"owner": current_user}

	def get_documents(self):
		"""Override to return test data instead of querying database."""
		return self.test_docs

	def add_test_doc(
		self, doctype, name, title=None, content=None, owner="Administrator", modified=None, **kwargs
	):
		"""Helper to add test documents."""
		doc = Mock()
		doc.doctype = doctype
		doc.name = name
		doc.title = title or f"Test {name}"
		doc.content = content or f"Content for {name}"
		doc.owner = owner
		doc.modified = modified or frappe.utils.now_datetime()

		# Add any additional fields
		for key, value in kwargs.items():
			setattr(doc, key, value)

		self.test_docs.append(doc)
		return doc


class TestFrappeSQLiteSearch(IntegrationTestCase):
	"""Test cases for SQLite FTS5 search functionality."""

	def setUp(self):
		self.search = TestSQLiteSearch()
		# Use temporary directory for test database
		self.temp_dir = tempfile.mkdtemp()
		self.search.db_path = os.path.join(self.temp_dir, "test_search.db")

	def tearDown(self):
		# Clean up test database
		if os.path.exists(self.search.db_path):
			os.unlink(self.search.db_path)
		if os.path.exists(self.temp_dir):
			os.rmdir(self.temp_dir)

	def test_initialization(self):
		"""Test basic initialization of search class."""
		self.assertEqual(self.search.db_name, "test_search.db")
		self.assertIsInstance(self.search.warnings, list)
		self.assertEqual(len(self.search.warnings), 0)

	def test_new_api_configuration(self):
		"""Test the new API configuration approach."""
		# Test class-level configuration is properly loaded
		self.assertTrue(hasattr(self.search, "INDEX_NAME"))
		self.assertTrue(hasattr(self.search, "INDEX_SCHEMA"))
		self.assertTrue(hasattr(self.search, "INDEXABLE_DOCTYPES"))

		# Test schema generation
		schema = self.search._get_schema()
		self.assertIn("text_fields", schema)
		self.assertIn("metadata_fields", schema)
		self.assertEqual(schema["text_fields"], ["title", "content"])  # Default text fields

		# Test automatic metadata fields
		metadata_fields = schema["metadata_fields"]
		self.assertIn("modified", metadata_fields)
		self.assertIn("doctype", metadata_fields)
		self.assertIn("name", metadata_fields)
		self.assertIn("owner", metadata_fields)
		self.assertIn("status", metadata_fields)

		# Test tokenizer
		self.assertEqual(schema["tokenizer"], "unicode61 remove_diacritics 2")

	def test_field_mapping_configuration(self):
		"""Test field mapping from new configuration format."""
		# Test document configurations are properly built
		configs = self.search.doc_configs
		self.assertIn("Note", configs)
		self.assertIn("ToDo", configs)

		# Test Note configuration
		note_config = configs["Note"]
		self.assertIn("fields", note_config)
		self.assertIn("field_mappings", note_config)
		self.assertEqual(note_config["content_field"], "content")
		self.assertEqual(note_config["title_field"], "title")
		self.assertEqual(note_config["modified_field"], "modified")

		# Test ToDo configuration with field mapping
		todo_config = configs["ToDo"]
		self.assertEqual(todo_config["content_field"], "description")
		self.assertEqual(todo_config["title_field"], "title")  # Default
		self.assertEqual(todo_config["modified_field"], "modified")
		self.assertEqual(todo_config["field_mappings"]["content"], "description")

	def test_document_configs_validation(self):
		"""Test validation of document configurations."""
		# Test valid configuration
		configs = self.search.doc_configs
		self.assertIn("Note", configs)
		self.assertIn("fields", configs["Note"])
		self.assertIn("content_field", configs["Note"])

		# Test invalid configuration - missing INDEXABLE_DOCTYPES
		class InvalidSearch(SQLiteSearch):
			INDEX_NAME = "test.db"
			INDEX_SCHEMA: ClassVar = {"metadata_fields": []}
			# Missing INDEXABLE_DOCTYPES

			def get_search_filters(self):
				return {}

		with self.assertRaises(ValueError) as cm:
			InvalidSearch()
		self.assertIn("INDEXABLE_DOCTYPES", str(cm.exception))

		# Test invalid configuration - missing fields
		class InvalidFieldsSearch(SQLiteSearch):
			INDEX_NAME = "test.db"
			INDEX_SCHEMA: ClassVar = {"metadata_fields": []}
			INDEXABLE_DOCTYPES: ClassVar = {
				"Invalid": {
					# Missing "fields" key
				}
			}

			def get_search_filters(self):
				return {}

		with self.assertRaises(ValueError) as cm:
			InvalidFieldsSearch()
		self.assertIn("fields", str(cm.exception))

	def test_fts_schema_validation(self):
		"""Test FTS schema configuration."""
		schema = self.search._get_schema()
		self.assertIn("text_fields", schema)
		self.assertIn("metadata_fields", schema)
		self.assertIsInstance(schema["text_fields"], list)
		self.assertIsInstance(schema["metadata_fields"], list)
		self.assertIn("text_fields", schema)
		self.assertIn("metadata_fields", schema)
		self.assertIsInstance(schema["text_fields"], list)
		self.assertIsInstance(schema["metadata_fields"], list)

	def test_search_disabled(self):
		"""Test behavior when search is disabled."""
		with patch.object(self.search, "is_search_enabled", return_value=False):
			result = self.search.search("test query")
			self.assertEqual(result["results"], [])
			self.assertEqual(result["summary"]["total_matches"], 0)

	def test_search_without_index(self):
		"""Test search raises error when index doesn't exist."""
		with self.assertRaises(SQLiteFTS5IndexMissingError):
			self.search.search("test query")

	def test_index_exists(self):
		"""Test index existence checking."""
		# Initially no index
		self.assertFalse(self.search.index_exists())

		# After building index
		self.search.add_test_doc("Note", "TEST-001", "Test Note", "Test content")
		self.search.build_index()
		self.assertTrue(self.search.index_exists())

	def test_build_index_basic(self):
		"""Test basic index building functionality."""
		# Add test documents
		self.search.add_test_doc("Note", "NOTE-001", "Important Note", "This is important content")
		self.search.add_test_doc("Note", "NOTE-002", "Another Note", "Different content here")
		self.search.add_test_doc("ToDo", "TODO-001", None, "Task description", status="Open")

		# Build index
		self.search.build_index()

		# Verify index was created
		self.assertTrue(self.search.index_exists())

		# Verify database tables exist
		conn = self.search._get_connection(read_only=True)
		try:
			cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
			tables = [row[0] for row in cursor.fetchall()]
			self.assertIn("search_fts", tables)
			self.assertIn("search_vocabulary", tables)
			self.assertIn("search_trigrams", tables)
		finally:
			conn.close()

	def test_search_basic_functionality(self):
		"""Test basic search functionality."""
		# Add test documents
		self.search.add_test_doc("Note", "NOTE-001", "Python Programming", "Learn Python basics")
		self.search.add_test_doc("Note", "NOTE-002", "JavaScript Guide", "JavaScript fundamentals")
		self.search.add_test_doc("Note", "NOTE-003", "Web Development", "HTML CSS JavaScript")

		# Build index
		self.search.build_index()

		# Test search
		results = self.search.search("Python")
		self.assertGreater(len(results["results"]), 0)
		self.assertEqual(results["summary"]["total_matches"], len(results["results"]))

		# Check result structure
		result = results["results"][0]
		self.assertIn("id", result)
		self.assertIn("title", result)
		self.assertIn("content", result)
		self.assertIn("score", result)
		self.assertIn("doctype", result)

	def test_search_with_filters(self):
		"""Test search with filters."""
		# Add test documents with different owners
		self.search.add_test_doc("Note", "NOTE-001", "Admin Note", "Admin content", owner="Administrator")
		self.search.add_test_doc("Note", "NOTE-002", "User Note", "User content", owner="test@example.com")

		# Build index
		self.search.build_index()

		# Test search with filter
		results = self.search.search("content", filters={"owner": "Administrator"})
		self.assertEqual(len(results["results"]), 1)
		self.assertEqual(results["results"][0]["author"], "Administrator")

	def test_search_title_only(self):
		"""Test title-only search."""
		# Add test documents
		self.search.add_test_doc("Note", "NOTE-001", "Python Guide", "JavaScript content")
		self.search.add_test_doc("Note", "NOTE-002", "JavaScript Guide", "Python content")

		# Build index
		self.search.build_index()

		# Test title-only search
		results = self.search.search("Python", title_only=True)

		# Should find only the document with Python in title
		self.assertEqual(len(results["results"]), 1)
		self.assertIn("Python", results["results"][0]["title"])

	def test_search_scoring(self):
		"""Test search result scoring."""
		now = time.time()
		recent_time = frappe.utils.get_datetime(now - 3600)  # 1 hour ago
		old_time = frappe.utils.get_datetime(now - 86400 * 30)  # 30 days ago

		# Add documents with different recency
		self.search.add_test_doc("Note", "NOTE-001", "Python Tutorial", "Learn Python", modified=recent_time)
		self.search.add_test_doc("Note", "NOTE-002", "Old Python Guide", "Python basics", modified=old_time)

		# Build index
		self.search.build_index()

		# Search for Python
		results = self.search.search("Python")

		# Recent document should score higher
		self.assertGreater(len(results["results"]), 1)
		scores = [r["score"] for r in results["results"]]
		# Results should be sorted by score descending
		self.assertEqual(scores, sorted(scores, reverse=True))

	def test_spelling_correction(self):
		"""Test spelling correction functionality."""
		# Add documents
		self.search.add_test_doc("Note", "NOTE-001", "Python Programming", "Programming in Python")
		self.search.add_test_doc("Note", "NOTE-002", "JavaScript Guide", "JavaScript development")

		# Build index
		self.search.build_index()

		# Test with misspelled query
		results = self.search.search("Pythjon")  # Misspelled "Python"

		# Should still find Python-related content
		if results["summary"]["corrected_words"]:
			self.assertIn("Pythjon", results["summary"]["corrected_words"])

	def test_warning_system(self):
		"""Test structured warning system."""
		# Add document with missing fields
		doc = Mock(spec=["doctype", "name", "modified", "owner"])
		doc.doctype = "Note"
		doc.name = "TEST-001"
		# Missing title and content fields
		doc.modified = frappe.utils.now_datetime()
		doc.owner = "Administrator"
		self.search.test_docs.append(doc)

		# Build index (should generate warnings)
		self.search.build_index()

		# Check warnings were generated
		self.assertGreater(len(self.search.warnings), 0)

		# Check warning structure
		warning = self.search.warnings[0]
		self.assertIsInstance(warning, IndexWarning)
		self.assertIsInstance(warning.type, WarningType)
		self.assertIsNotNone(warning.message)

	def test_warning_statistics(self):
		"""Test warning statistics functionality."""
		# Manually add some warnings
		self.search._warn_missing_text_fields("Note", "TEST-001", ["title", "content"])
		self.search._warn_missing_content_field("Note", "TEST-002", "content")
		self.search._warn_invalid_document({"name": None}, "missing name")

		# Get statistics
		stats = self.search.get_warning_statistics()

		self.assertEqual(stats["total"], 3)
		self.assertIn("missing_text_fields", stats["by_type"])
		self.assertIn("missing_content_field", stats["by_type"])
		self.assertIn("invalid_document", stats["by_type"])

		# Check counts
		self.assertEqual(stats["by_type"]["missing_text_fields"]["count"], 1)
		self.assertEqual(stats["by_type"]["missing_content_field"]["count"], 1)
		self.assertEqual(stats["by_type"]["invalid_document"]["count"], 1)

	def test_trigram_generation(self):
		"""Test trigram generation for fuzzy matching."""
		trigrams = self.search._generate_trigrams("python")
		expected = ["  p", " py", "pyt", "yth", "tho", "hon", "on ", "n  "]
		self.assertEqual(trigrams, expected)

	def test_fts_query_preparation(self):
		"""Test FTS query preparation."""
		# Simple query
		query = self.search._prepare_fts_query("python programming")
		self.assertIn("python", query)
		self.assertIn("programming", query)

		# Query with special characters
		query = self.search._prepare_fts_query('python "advanced"')
		self.assertIn('""advanced""', query)  # Should escape quotes

	def test_content_processing(self):
		"""Test HTML content processing."""
		html_content = '<p>This is <b>bold</b> text with <a href="http://example.com">link</a></p>'
		processed = self.search._process_content(html_content)

		# Should remove HTML tags
		self.assertNotIn("<p>", processed)
		self.assertNotIn("<b>", processed)
		self.assertNotIn("<a", processed)

		# Should contain text content
		self.assertIn("This is", processed)
		self.assertIn("bold", processed)
		self.assertIn("text", processed)

		# Should replace links
		self.assertIn("[link]", processed)

	def test_database_connection(self):
		"""Test database connection handling."""
		# Test successful connection
		conn = self.search._get_connection()
		self.assertIsNotNone(conn)
		conn.close()

		# Test read-only connection
		conn = self.search._get_connection(read_only=True)
		self.assertIsNotNone(conn)
		conn.close()

	def test_permission_filters(self):
		"""Test permission filter application."""
		# Add documents with different owners
		self.search.add_test_doc("Note", "NOTE-001", "Public Note", "Public content", owner="Administrator")
		self.search.add_test_doc("Note", "NOTE-002", "User Note", "User content", owner="test@example.com")

		# Build index
		self.search.build_index()

		# Test with different users
		with patch.object(frappe, "session", {"user": "test@example.com"}):
			# Create new search instance to get fresh permission filters
			search_user = TestSQLiteSearch()
			search_user.db_path = self.search.db_path  # Use same database

			results = search_user.search("content")
			# Should only see documents owned by test user
			self.assertEqual(len(results["results"]), 1)
			self.assertEqual(results["results"][0]["author"], "test@example.com")

	def test_permission_filter_with_empty_list(self):
		"""Test that an empty list in permission filters returns no results."""
		# Add a test document that would normally be found
		self.search.add_test_doc("Note", "NOTE-001", "Searchable Note", "This content is searchable.")
		self.search.build_index()

		# Override search filters to return an empty list, simulating no access
		with patch.object(self.search, "get_search_filters", return_value={"owner": []}):
			results = self.search.search("searchable")
			# The query should return no results due to the empty permission filter
			self.assertEqual(len(results["results"]), 0)
			self.assertEqual(results["summary"]["total_matches"], 0)

	def test_single_document_operations(self):
		"""Test indexing and removing single documents."""
		# Build initial index
		self.search.add_test_doc("Note", "NOTE-001", "Initial Note", "Initial content")
		self.search.build_index()

		# Test single document indexing (mock the frappe.enqueue call)
		with patch("frappe.enqueue") as mock_enqueue:
			doc = Mock()
			doc.doctype = "Note"
			doc.name = "NOTE-002"

			self.search.index_doc(doc)
			mock_enqueue.assert_called_once()

			# Test document removal
			self.search.remove_doc(doc)
			self.assertEqual(mock_enqueue.call_count, 2)

	def test_empty_search_result(self):
		"""Test empty search result structure."""
		result = self.search._empty_search_result()

		self.assertEqual(result["results"], [])
		self.assertEqual(result["summary"]["total_matches"], 0)
		self.assertEqual(result["summary"]["filtered_matches"], 0)
		self.assertEqual(result["summary"]["duration"], 0)
		self.assertIsInstance(result["summary"]["applied_filters"], dict)

	def test_advanced_scoring_calculation(self):
		"""Test advanced scoring calculation."""
		# Mock row data
		row = {
			"bm25_score": -1.5,
			"original_title": "Python Programming Guide",
			"timestamp": time.time() - 3600,  # 1 hour ago
			"doctype": "Note",
		}

		query = "Python programming"
		query_words = query.split()

		score = self.search._calculate_advanced_score(row, query, query_words)

		# Score should be positive and reasonable
		self.assertGreater(score, 0)
		self.assertLess(score, 100)  # Sanity check

	def test_atomic_index_building(self):
		"""Test atomic index building with temporary database."""
		# Add test data
		self.search.add_test_doc("Note", "NOTE-001", "Test Note", "Test content")

		# Mock progress bar to avoid issues in test
		with patch("frappe.utils.update_progress_bar"):
			# Build index
			self.search.build_index()

		# Verify final database exists
		self.assertTrue(os.path.exists(self.search.db_path))

		# Verify temp database was cleaned up
		temp_path = self.search.db_path.replace(".db", ".temp.db")
		self.assertFalse(os.path.exists(temp_path))

	def test_configuration_validation_errors(self):
		"""Test various configuration validation errors."""

		# Test missing content field in fields list
		class InvalidContentFieldSearch(SQLiteSearch):
			INDEX_NAME = "test.db"
			INDEX_SCHEMA: ClassVar = {"metadata_fields": []}
			INDEXABLE_DOCTYPES: ClassVar = {
				"Note": {
					"fields": ["name", "title", "modified"],  # Missing content field
				}
			}

			def get_search_filters(self):
				return {}

		with self.assertRaises(ValueError) as cm:
			InvalidContentFieldSearch()
		# This should fail because content field is not in fields list

		# Test invalid field definition
		class InvalidFieldDefSearch(SQLiteSearch):
			INDEX_NAME = "test.db"
			INDEX_SCHEMA: ClassVar = {"metadata_fields": []}
			INDEXABLE_DOCTYPES: ClassVar = {
				"Note": {
					"fields": ["name", "title", 123],  # Invalid field type
				}
			}

			def get_search_filters(self):
				return {}

		with self.assertRaises(ValueError) as cm:
			InvalidFieldDefSearch()
		# This should fail because field definition is invalid

		# Test missing INDEX_SCHEMA
		class MissingSchemaSearch(SQLiteSearch):
			INDEX_NAME = "test.db"
			INDEXABLE_DOCTYPES: ClassVar = {
				"Note": {
					"fields": ["name", "title", "content"],
				}
			}

			def get_search_filters(self):
				return {}

		with self.assertRaises(ValueError) as cm:
			MissingSchemaSearch()
		self.assertIn("INDEX_SCHEMA", str(cm.exception))

	def test_warning_summary_output(self):
		"""Test warning summary output formatting."""
		# Add various types of warnings
		self.search._warn_missing_text_fields("Note", "TEST-001", ["title"])
		self.search._warn_missing_content_field("Note", "TEST-002", "content")
		self.search._warn_invalid_document({"name": None}, "missing name")

		# Capture output
		import io
		from contextlib import redirect_stdout

		f = io.StringIO()
		with redirect_stdout(f):
			self.search._print_warning_summary()

		output = f.getvalue()

		# Check output contains expected sections
		self.assertIn("SEARCH INDEX BUILD WARNINGS", output)
		self.assertIn("Missing Text Fields", output)
		self.assertIn("Missing Content Field", output)
		self.assertIn("Invalid Documents", output)
		self.assertIn("Total warnings: 3", output)

	def test_timestamp_conditional_logic(self):
		"""Test that modified-related logic is conditionally applied based on schema."""

		# Test search class with modified in schema
		class SearchWithModified(TestSQLiteSearch):
			INDEX_SCHEMA: ClassVar = {
				"metadata_fields": ["modified", "owner"],
				"tokenizer": "unicode61 remove_diacritics 2",
			}

		# Test search class without modified in schema
		class SearchWithoutModified(TestSQLiteSearch):
			INDEX_SCHEMA: ClassVar = {
				"metadata_fields": ["owner"],  # No modified
				"tokenizer": "unicode61 remove_diacritics 2",
			}

			INDEXABLE_DOCTYPES: ClassVar = {
				"Note": {
					"fields": ["name", "title", "content", "owner"],  # No modified field
					"filters": {},
				},
				"ToDo": {
					"fields": [
						"name",
						"title",
						{"content": "description"},
						"status",
						"owner",
					],  # No modified field
					"filters": {"status": ("!=", "Deleted")},
				},
			}

		# Test scoring pipeline includes recency boost only when modified is present
		search_with_modified = SearchWithModified()
		pipeline_with_modified = search_with_modified.get_scoring_pipeline()
		method_names_with_modified = [method.__name__ for method in pipeline_with_modified]

		search_without_modified = SearchWithoutModified()
		pipeline_without_modified = search_without_modified.get_scoring_pipeline()
		method_names_without_modified = [method.__name__ for method in pipeline_without_modified]

		# Verify recency boost is included only when modified is present
		self.assertIn("_get_recency_boost", method_names_with_modified)
		self.assertNotIn("_get_recency_boost", method_names_without_modified)

		# Verify pipeline lengths
		self.assertEqual(len(pipeline_with_modified), 3)  # base_score, title_boost, recency_boost
		self.assertEqual(len(pipeline_without_modified), 2)  # base_score, title_boost

		# Test that recency boost returns 1.0 when modified is missing from row
		row_without_modified = {"title": "Test", "content": "Content"}
		boost = search_with_modified._get_recency_boost(row_without_modified, "query")
		self.assertEqual(boost, 1.0)

		# Test with None modified
		row_with_none_modified = {"title": "Test", "content": "Content", "modified": None}
		boost = search_with_modified._get_recency_boost(row_with_none_modified, "query")
		self.assertEqual(boost, 1.0)

		# Test document preparation - modified should only be added if in schema
		doc = Mock()
		doc.doctype = "Note"
		doc.name = "TEST-001"
		doc.title = "Test Title"
		doc.content = "Test Content"
		doc.modified = frappe.utils.now_datetime()
		doc.owner = "Administrator"

		# With modified in schema
		search_with_modified.test_docs = [doc]
		prepared_doc_with_modified = search_with_modified.prepare_document(doc)
		self.assertIn("modified", prepared_doc_with_modified)
		self.assertIsNotNone(prepared_doc_with_modified["modified"])

		# Without modified in schema
		search_without_modified.test_docs = [doc]
		prepared_doc_without_modified = search_without_modified.prepare_document(doc)
		self.assertNotIn("modified", prepared_doc_without_modified)

	def test_no_warnings_summary(self):
		"""Test warning summary when no warnings exist."""
		import io
		from contextlib import redirect_stdout

		f = io.StringIO()
		with redirect_stdout(f):
			self.search._print_warning_summary()

		output = f.getvalue()
		# Should produce no output
		self.assertEqual(output.strip(), "")


class TestFrappeSQLiteSearchEdgeCases(IntegrationTestCase):
	"""Test edge cases and error conditions."""

	def setUp(self):
		self.search = TestSQLiteSearch()
		self.temp_dir = tempfile.mkdtemp()
		self.search.db_path = os.path.join(self.temp_dir, "test_search.db")

	def tearDown(self):
		if os.path.exists(self.search.db_path):
			os.unlink(self.search.db_path)
		if os.path.exists(self.temp_dir):
			os.rmdir(self.temp_dir)

	def test_empty_query_search(self):
		"""Test search with empty query."""
		self.search.add_test_doc("Note", "NOTE-001", "Test", "Content")
		self.search.build_index()

		result = self.search.search("")
		self.assertEqual(result["results"], [])
		self.assertEqual(result["summary"]["total_matches"], 0)

		result = self.search.search(None)
		self.assertEqual(result["results"], [])

	def test_search_with_no_documents(self):
		"""Test search when no documents are indexed."""
		self.search.build_index()  # Build empty index

		result = self.search.search("test")
		self.assertEqual(result["results"], [])
		self.assertEqual(result["summary"]["total_matches"], 0)

	def test_malformed_document_handling(self):
		"""Test handling of malformed documents during indexing."""
		# Add document without required fields
		doc = Mock()
		doc.doctype = None  # Missing doctype
		doc.name = "TEST-001"
		self.search.test_docs.append(doc)

		# Should not crash during indexing
		self.search.build_index()

		# Should generate warnings
		self.assertGreater(len(self.search.warnings), 0)
		warning_types = [w.type for w in self.search.warnings]
		self.assertIn(WarningType.MISSING_DOCTYPE, warning_types)

	def test_database_error_handling(self):
		"""Test handling of database connection errors."""
		# Point to invalid database path
		self.search.db_path = "/invalid/path/search.db"

		with self.assertRaises(SQLiteFTS5IndexMissingError):
			self.search._get_connection()

	def test_very_short_words_in_similarity(self):
		"""Test similarity calculation with very short words."""
		# Build index first so tables exist
		self.search.add_test_doc("Note", "NOTE-001", "Test Note", "Test content")
		self.search.build_index()

		similar = self.search._find_similar_words("ab")  # Too short
		self.assertEqual(similar, [])

		similar = self.search._find_similar_words("the")  # Exactly minimum length
		# Should work but may return empty if no vocabulary built
		self.assertIsInstance(similar, list)

	def test_special_characters_in_content(self):
		"""Test handling of special characters in content."""
		special_content = "Content with émojis 😊 and spëcial châractérs"
		processed = self.search._process_content(special_content)

		# Should handle unicode characters gracefully
		self.assertIsInstance(processed, str)
		self.assertIn("Content", processed)

	def test_large_document_handling(self):
		"""Test handling of very large documents."""
		# Create large content
		large_content = "Large content " * 10000  # ~130KB content

		self.search.add_test_doc("Note", "LARGE-001", "Large Document", large_content)

		# Should handle large documents without issues
		self.search.build_index()

		# Should be able to search large documents
		results = self.search.search("Large")
		self.assertGreater(len(results["results"]), 0)

	def test_concurrent_database_access(self):
		"""Test concurrent database access patterns."""
		self.search.add_test_doc("Note", "NOTE-001", "Test", "Content")
		self.search.build_index()

		# Simulate multiple connections
		conn1 = self.search._get_connection(read_only=True)
		conn2 = self.search._get_connection(read_only=True)

		try:
			# Both connections should work
			cursor1 = conn1.execute("SELECT COUNT(*) FROM search_fts")
			count1 = cursor1.fetchone()[0]

			cursor2 = conn2.execute("SELECT COUNT(*) FROM search_fts")
			count2 = cursor2.fetchone()[0]

			self.assertEqual(count1, count2)

		finally:
			conn1.close()
			conn2.close()


class TestFieldMappingEdgeCases(IntegrationTestCase):
	"""Test edge cases in field mapping configuration."""

	def test_mixed_field_definitions(self):
		"""Test mixed field definitions in INDEXABLE_DOCTYPES."""

		# Test mixed field definitions
		class MixedFieldSearch(SQLiteSearch):
			INDEX_NAME = "test.db"
			INDEX_SCHEMA: ClassVar = {"metadata_fields": ["custom_field"], "tokenizer": "unicode61"}
			INDEXABLE_DOCTYPES: ClassVar = {
				"TestDoc": {
					"fields": [
						"name",
						"title",
						{"content": "description"},  # Mapped field
						{"modified": "last_updated"},  # Mapped field
						"owner",  # Direct field
					],
				}
			}

			def get_search_filters(self):
				return {}

		search = MixedFieldSearch()

		# Test configuration was built correctly
		config = search.doc_configs["TestDoc"]
		self.assertEqual(config["content_field"], "description")
		self.assertEqual(config["modified_field"], "last_updated")
		self.assertEqual(config["field_mappings"]["content"], "description")
		self.assertEqual(config["field_mappings"]["modified"], "last_updated")

		# Test fields list contains all fields
		fields = config["fields"]
		self.assertIn("name", fields)
		self.assertIn("title", fields)
		self.assertIn("description", fields)
		self.assertIn("last_updated", fields)
		self.assertIn("owner", fields)
