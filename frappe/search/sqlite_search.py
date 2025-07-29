# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import datetime
import inspect
import os
import re
import sqlite3
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Any

from bs4 import BeautifulSoup

import frappe
from frappe.model.document import Document
from frappe.utils import update_progress_bar


class WarningType(Enum):
	"""Warning types for search indexing."""

	INVALID_DOCUMENT = "invalid_document"
	MISSING_TEXT_FIELDS = "missing_text_fields"
	MISSING_CONTENT_FIELD = "missing_content_field"
	MISSING_TITLE_FIELD = "missing_title_field"
	MISSING_DOCTYPE = "missing_doctype"
	MISSING_NAME = "missing_name"
	OTHER = "other"


@dataclass
class IndexWarning:
	"""Structured warning for search indexing."""

	type: WarningType
	message: str
	doctype: str | None = None
	docname: str | None = None
	field: str | None = None
	missing_fields: list | None = None

	def __str__(self):
		return self.message


class SQLiteSearchIndexMissingError(Exception):
	pass


# Search Configuration Constants
MAX_SEARCH_RESULTS = 100
SNIPPET_LENGTH = 64
MIN_WORD_LENGTH = 4
MAX_EDIT_DISTANCE = 3
MIN_SIMILARITY_THRESHOLD = 0.6
MAX_SPELLING_SUGGESTIONS = 3
SIMILARITY_TRIGRAM_WEIGHT = 0.7
SIMILARITY_SEQUENCE_WEIGHT = 0.3
FREQUENCY_BOOST_FACTOR = 1000
MAX_FREQUENCY_BOOST = 1.2
RECENCY_DECAY_RATE = 0.005  # Linear decay per day beyond 90 days
MIN_RECENCY_BOOST = 0.5
TITLE_EXACT_MATCH_BOOST = 5.0
TITLE_PARTIAL_MATCH_BOOST = 2.0
DISCUSSION_BOOST = 1.2
COMMENT_BOOST = 1.0

# Time-based recency categories for aggressive boosting
RECENT_HOURS_BOOST = 1.8  # Documents from last 24 hours
RECENT_WEEK_BOOST = 1.5  # Documents from last 7 days
RECENT_MONTH_BOOST = 1.2  # Documents from last 30 days
RECENT_QUARTER_BOOST = 1.1  # Documents from last 90 days


class SQLiteSearch(ABC):
	"""
	Abstract base class for SQLite FTS5-based full-text search for Frappe.

	Provides full-text search with advanced features:
	- Spelling correction using trigram similarity
	- Time-based recency boost with categorical scoring
	- Custom scoring with title matching and document type boosts
	- Ranking tracking (original BM25 vs modified scores)
	- Filtering by user-defined criteria
	- Permission-aware search results via query-level filtering
	"""

	@staticmethod
	def scoring_function(func):
		"""
		Decorator to mark methods as scoring functions that should be automatically
		included in the scoring pipeline.

		Usage:
		    @SQLiteSearch.scoring_function
		    def custom_boost(self, row, query, query_words):
		        return 1.5
		"""
		func._is_scoring_function = True
		return func

	def __init__(self, db_name=None):
		# Use class-level INDEX_NAME if db_name not provided
		if db_name is None:
			db_name = getattr(self, "INDEX_NAME", "search.db")

		self.db_name = db_name
		self.db_path = self._get_db_path()

		# Validate required class attributes early
		if not hasattr(self, "INDEX_SCHEMA"):
			raise ValueError("INDEX_SCHEMA must be defined as a class-level variable")
		if not hasattr(self, "INDEXABLE_DOCTYPES"):
			raise ValueError("INDEXABLE_DOCTYPES must be defined as a class-level variable")

		self.doc_configs = self._build_doc_configs()
		self.warnings: list[IndexWarning] = []  # Collect warnings during indexing
		self.schema = self._get_schema()
		self._validate_config()

	# Helper Methods for New API

	def _parse_doctype_fields(self, doctype, config):
		"""Parse field definitions for a doctype to extract field names and mappings."""
		if "fields" not in config:
			raise ValueError(f"Missing 'fields' in configuration for doctype '{doctype}'")

		parsed_fields = []
		field_mappings = {}

		for field_def in config["fields"]:
			if isinstance(field_def, str):
				parsed_fields.append(field_def)
			elif isinstance(field_def, dict):
				for schema_field, doctype_field in field_def.items():
					parsed_fields.append(doctype_field)
					field_mappings[schema_field] = doctype_field
			else:
				raise ValueError(f"Invalid field definition: {field_def}")

		return parsed_fields, field_mappings

	def _build_doc_configs(self):
		"""Build document configurations from class-level INDEXABLE_DOCTYPES."""
		doc_configs = {}
		for doctype, config in self.INDEXABLE_DOCTYPES.items():
			parsed_fields, field_mappings = self._parse_doctype_fields(doctype, config)

			# Determine content field
			content_field = field_mappings.get("content")
			if not content_field:
				if "content" in parsed_fields:
					content_field = "content"
				else:
					raise ValueError(
						f"Content field must be present in fields list or explicitly mapped for '{doctype}'"
					)

			# Determine title field
			title_field = field_mappings.get("title")
			if not title_field and "title" in parsed_fields:
				title_field = "title"

			doc_configs[doctype] = {
				"fields": parsed_fields,
				"field_mappings": field_mappings,
				"content_field": content_field,
				"title_field": title_field,
				"modified_field": field_mappings.get("modified", "modified"),
				"filters": config.get("filters", {}),
			}

		return doc_configs

	def _get_schema(self):
		"""Get the search index schema with automatic defaults."""
		if not hasattr(self, "INDEX_SCHEMA"):
			raise ValueError("INDEX_SCHEMA must be defined as a class-level variable")

		schema = self.INDEX_SCHEMA.copy()

		# Default text fields to title and content
		schema.setdefault("text_fields", ["title", "content"])

		# Default tokenizer
		schema.setdefault("tokenizer", "unicode61 remove_diacritics 2")

		# Automatically add required metadata fields
		metadata_fields = schema.setdefault("metadata_fields", [])
		required_fields = ["doctype", "name"]

		for field in required_fields:
			if field not in metadata_fields:
				metadata_fields.append(field)

		# Add 'modified' to metadata if it's used in the schema or any doctype config
		is_modified_in_schema = "modified" in self.INDEX_SCHEMA.get("metadata_fields", [])
		is_modified_in_doctypes = any(
			"modified" in config.get("field_mappings", {}) or "modified" in config.get("fields", [])
			for config in self.doc_configs.values()
		)

		if (is_modified_in_schema or is_modified_in_doctypes) and "modified" not in metadata_fields:
			metadata_fields.append("modified")

		schema["metadata_fields"] = metadata_fields

		return schema

	# Abstract Method - Must be implemented by subclasses

	@abstractmethod
	def get_search_filters(self):
		"""
		Return filters to apply to search results.

		Returns:
		    dict: Permission filters in format:
		        {
		            "field_name": value,  # Single value: field = value
		            "field_name": [val1, val2]  # List: field IN (val1, val2)
		        }
		"""
		pass

	# Public API Methods

	def search(self, query, title_only=False, filters=None):
		"""
		Main search method with advanced filtering support.

		Args:
		    query (str): Search query text
		    title_only (bool): Whether to search only in titles
		    filters (dict): Optional filters by field names

		Returns:
		    dict: Search results with summary statistics
		"""
		if not self.is_search_enabled():
			return self._empty_search_result(title_only, filters)

		self.raise_if_not_indexed()

		if not query:
			return self._empty_search_result(title_only, filters)

		start_time = time.time()

		# Prepare filters if provided
		filters = filters or {}

		# Get permission filters from subclass
		permission_filters = self.get_search_filters()

		# Combine user filters with permission filters
		all_filters = {**filters, **permission_filters}

		# Prepare FTS5 query with spelling correction
		expanded_query, corrections = self._expand_query_with_corrections(query)
		fts_query = self._prepare_fts_query(expanded_query)

		try:
			raw_results = self._execute_search_query(fts_query, title_only, all_filters)
			total_matches = len(raw_results)
		except sqlite3.Error as e:
			frappe.log_error(f"Search query failed: {e}")
			raw_results = []
			total_matches = 0

		# Process results
		processed_results = self._process_search_results(raw_results, query)

		duration = time.time() - start_time

		return {
			"results": processed_results,
			"summary": {
				"duration": round(duration, 3),
				"total_matches": total_matches,
				"returned_matches": total_matches,
				"corrected_words": corrections,
				"corrected_query": expanded_query if corrections else None,
				"title_only": title_only,
				"filtered_matches": len(processed_results),
				"applied_filters": filters,
			},
		}

	def build_index(self):
		"""Build the complete search index from scratch using atomic replacement."""
		if not self.is_search_enabled():
			return

		# Use temporary database path for atomic replacement
		temp_db_path = self._get_db_path(is_temp=True)
		original_db_path = self.db_path

		# Remove temp file if it exists
		if os.path.exists(temp_db_path):
			os.unlink(temp_db_path)

		# Temporarily switch to temp database for building
		self.db_path = temp_db_path

		try:
			self._update_progress("Setting up search tables", 0, 100, absolute=True)

			# Setup tables in temp database
			self._ensure_fts_table()

			self._update_progress("Fetching records", 20, 100, absolute=True)

			records = self.get_documents()
			documents = []

			self._update_progress("Preparing documents", 30, 100, absolute=True)

			total_records = len(records)
			for i, doc in enumerate(records):
				document = self.prepare_document(doc)
				if document:
					documents.append(document)

				# Update progress during document preparation
				if i % 100 == 0:
					progress = 30 + int((i / total_records) * 20)  # 30-50% range
					self._update_progress("Preparing documents", progress, 100, absolute=True)

			self._update_progress("Indexing documents", 50, 100, absolute=True)

			self._index_documents(documents)

			self._update_progress("Building spell correction vocabulary", 80, 100, absolute=True)

			# Build vocabulary for spelling correction
			self._build_vocabulary(documents)

			# Atomic replacement: move temp database to final location
			if os.path.exists(original_db_path):
				os.unlink(original_db_path)
			os.rename(temp_db_path, original_db_path)

			self._update_progress("Search index build complete", 100, 100, absolute=True)

			# Print warning summary
			self._print_warning_summary()

		except Exception:
			# Clean up temp file on error
			if os.path.exists(temp_db_path):
				os.unlink(temp_db_path)
			raise
		finally:
			# Restore original database path
			self.db_path = original_db_path

	# Status and Validation Methods

	def index_exists(self):
		"""Check if FTS index exists."""
		if not os.path.exists(self.db_path):
			return False

		try:
			result = self.sql(
				"SELECT name FROM sqlite_master WHERE type='table' AND name='search_fts'", read_only=True
			)
			return bool(result)
		except sqlite3.Error:
			return False

	def drop_index(self):
		"""Drop the search index by removing the database file."""
		if os.path.exists(self.db_path):
			try:
				os.unlink(self.db_path)
			except OSError as e:
				frappe.log_error(f"Failed to remove search index file {self.db_path}: {e}")
				raise

	def is_search_enabled(self):
		"""Override this to enable/disable search"""
		return True

	def raise_if_not_indexed(self):
		"""Raise exception if search index doesn't exist."""
		if not self.index_exists():
			raise SQLiteSearchIndexMissingError("Search index does not exist. Please build the index first.")

	def get_documents(self):
		"""Get all records to be indexed."""
		records = []
		for doctype, config in self.doc_configs.items():
			docs = frappe.qb.get_query(
				doctype, fields=config["fields"], filters=config.get("filters", {})
			).run(as_dict=True)

			for doc in docs:
				doc.doctype = doctype
				if config["modified_field"] != "modified":
					doc.modified = getattr(doc, config["modified_field"], None) or doc.modified
				records.append(doc)

		return records

	# Private Implementation Methods

	def _execute_search_query(self, fts_query, title_only, filters):
		"""Execute the FTS search query with optional filters."""
		# Build filter conditions
		filter_conditions = []
		filter_params = []

		if filters:
			# Build filter conditions dynamically
			for field, values in filters.items():
				if not values and isinstance(values, list):
					# If filter is an empty list, it should not match any documents.
					filter_conditions.append("1=0")
					continue

				if not values:  # Skip empty filters
					continue

				if isinstance(values, list):
					if len(values) == 1:
						filter_conditions.append(f"{field} = ?")
						filter_params.append(values[0])
					else:
						placeholders = ",".join(["?" for _ in values])
						filter_conditions.append(f"{field} IN ({placeholders})")
						filter_params.extend(values)
				else:
					filter_conditions.append(f"{field} = ?")
					filter_params.append(values)

		# Combine filter conditions with AND
		filter_clause = ""
		if filter_conditions:
			filter_clause = "AND " + " AND ".join(filter_conditions)

		# Get schema to build dynamic SELECT fields
		text_fields = self.schema["text_fields"]
		metadata_fields = self.schema["metadata_fields"]

		# Build SELECT clause with all fields
		select_fields = []

		# Add title highlighting
		title_field = "title" if "title" in text_fields else text_fields[0] if text_fields else "doc_id"
		title_column_index = self._get_text_field_column_index(title_field)
		if title_column_index is not None:
			select_fields.append(f"highlight(search_fts, {title_column_index}, '<mark>', '</mark>') as title")
		else:
			select_fields.append(f"{title_field} as title")

		# Add content snippet or highlighting
		if not title_only and "content" in text_fields:
			content_index = self._get_text_field_column_index("content")
			select_fields.append(
				f"snippet(search_fts, {content_index}, '<mark>', '</mark>', '...', ?) as content"
			)
		elif "content" in text_fields:
			select_fields.append("content")

		# Add all other fields
		for field in metadata_fields:
			if field != "doc_id":  # Already handled above
				select_fields.append(field)

		# Add scoring fields
		select_fields.extend(["bm25(search_fts) as bm25_score", f"{title_field} as original_title"])

		select_clause = ",\n                    ".join(select_fields)

		if title_only:
			sql = f"""
                SELECT
                    doc_id,
                    {select_clause}
                FROM search_fts
                WHERE search_fts MATCH ?
                AND {title_field} MATCH ?
                {filter_clause}
                ORDER BY bm25_score
                LIMIT ?
            """
			return self.sql(sql, (fts_query, fts_query, *filter_params, MAX_SEARCH_RESULTS), read_only=True)
		else:
			params = []
			if "content" in text_fields:
				params.append(SNIPPET_LENGTH)
			params.extend([fts_query, *filter_params, MAX_SEARCH_RESULTS])

			sql = f"""
                SELECT
                    doc_id,
                    {select_clause}
                FROM search_fts
                WHERE search_fts MATCH ?
                {filter_clause}
                ORDER BY bm25_score
                LIMIT ?
            """
			return self.sql(sql, params, read_only=True)

	def _process_search_results(self, raw_results, query):
		"""Process search results with scoring."""
		processed_results = []
		query_words = query.split()

		# Get schema configuration
		text_fields = self.schema["text_fields"]
		metadata_fields = self.schema["metadata_fields"]

		# 1-based ranking
		for original_rank, row in enumerate(raw_results, 1):
			# Apply advanced heuristics scoring
			score = self._calculate_advanced_score(row, query, query_words)

			# Build result dynamically based on schema
			result = {
				"id": row["doc_id"],
				"score": score,
				"original_rank": original_rank,
				"bm25_score": row["bm25_score"],
			}

			# Add text fields
			for field in text_fields:
				result[field] = row[field] if field in row.keys() else ""

			# Add metadata fields
			for field in metadata_fields:
				if field == "owner":
					# Map owner to author for backward compatibility
					result["author"] = row["owner"] if "owner" in row.keys() else ""
				else:
					result[field] = row[field] if field in row.keys() else None

			processed_results.append(result)

		# Sort by custom score (descending - higher is better)
		processed_results.sort(key=lambda x: x["score"], reverse=True)

		# Add modified ranking after custom scoring
		for i, result in enumerate(processed_results):
			result["modified_rank"] = i + 1

		return processed_results

	def get_scoring_pipeline(self):
		"""
		Return the scoring pipeline, a list of methods to calculate the final score.
		Each method in the list should accept either (row, query) or (row, query, query_words)
		and return a float. The final score is the product of all values returned by the pipeline methods.
		Subclasses can override this to customize the scoring logic.
		"""
		pipeline = [
			self._get_base_score,
			self._get_title_boost,
		]

		# Only add recency boost if modified is available in the schema
		if "modified" in self.schema["metadata_fields"]:
			pipeline.append(self._get_recency_boost)

		# Automatically discover and add decorated scoring functions
		for attr_name in dir(self):
			attr = getattr(self, attr_name)
			if callable(attr) and hasattr(attr, "_is_scoring_function"):
				pipeline.append(attr)

		return pipeline

	def _calculate_advanced_score(self, row, query, query_words):
		"""
		Calculate the final score by executing the scoring pipeline.
		The final score is the product of all scores returned by the pipeline methods.
		"""
		pipeline = self.get_scoring_pipeline()
		final_score = 1.0

		for scoring_method in pipeline:
			# Check method signature to determine how to call it
			sig = inspect.signature(scoring_method)
			params = list(sig.parameters.keys())

			# Skip 'self' parameter
			if params and params[0] == "self":
				params = params[1:]

			# Call method based on its signature
			if len(params) >= 3 or "query_words" in params:
				# Method accepts query_words parameter
				final_score *= scoring_method(row, query, query_words)
			else:
				# Method only accepts row and query
				final_score *= scoring_method(row, query)

		return final_score

	def _get_base_score(self, row, query):
		"""Calculate the base score from BM25."""
		bm25_score = abs(row["bm25_score"]) if row["bm25_score"] is not None else 0
		return 1.0 / (1.0 + bm25_score) if bm25_score > 0 else 0.5

	def _get_title_boost(self, row, query, query_words):
		"""Calculate the title matching boost based on percentage of words matched."""
		original_title = (row["original_title"] or "").lower()
		query_lower = query.lower()

		# Check for exact phrase match first (highest boost)
		if query_lower in original_title:
			return TITLE_EXACT_MATCH_BOOST

		# Calculate percentage of query words that match in title
		if not query_words:
			return 1.0

		matched_words = 0
		for word in query_words:
			if word.lower() in original_title:
				matched_words += 1

		if matched_words == 0:
			return 1.0

		# Calculate match percentage
		match_percentage = matched_words / len(query_words)

		# Scale the boost between TITLE_PARTIAL_MATCH_BOOST (2.0) and TITLE_EXACT_MATCH_BOOST (5.0)
		# based on the percentage of words matched
		min_boost = TITLE_PARTIAL_MATCH_BOOST  # 2.0
		max_boost = TITLE_EXACT_MATCH_BOOST  # 5.0

		# Linear interpolation: boost = min_boost + (max_boost - min_boost) * match_percentage
		boost = min_boost + (max_boost - min_boost) * match_percentage

		return boost

	def _get_recency_boost(self, row, query):
		"""Calculate the time-based recency boost."""
		# Return neutral boost if modified is not available
		if "modified" not in row or row["modified"] is None:
			return 1.0

		current_time = time.time()
		doc_timestamp = row["modified"]
		hours_old = (current_time - doc_timestamp) / 3600
		days_old = hours_old / 24

		if hours_old <= 24:
			return RECENT_HOURS_BOOST
		if days_old <= 7:
			return RECENT_WEEK_BOOST
		if days_old <= 30:
			return RECENT_MONTH_BOOST
		if days_old <= 90:
			return RECENT_QUARTER_BOOST

		# Older documents get linear decay
		days_beyond_90 = days_old - 90
		return max(MIN_RECENCY_BOOST, RECENT_QUARTER_BOOST - (days_beyond_90 * RECENCY_DECAY_RATE))

	def _get_text_field_column_index(self, field_name):
		"""Get the 1-based column index of a text field in the FTS table."""
		try:
			# FTS table columns are doc_id, then text_fields...
			# So index is 1 (for doc_id) + index in text_fields list
			return 1 + self.schema["text_fields"].index(field_name)
		except ValueError:
			return None

	# Spelling Correction Methods

	def _expand_query_with_corrections(self, query):
		"""Expand query with spelling corrections."""
		words = query.strip().split()
		expanded_terms = []
		corrections = {}

		for word in words:
			similar_words = self._find_similar_words(word)
			if similar_words and similar_words[0] != word:
				# Replace the misspelled word with the corrected word
				corrected_word = similar_words[0]
				expanded_terms.append(corrected_word)
				corrections[word] = corrected_word
			else:
				expanded_terms.append(word)

		expanded_query = " ".join(expanded_terms)
		return expanded_query, corrections if corrections else None

	def _find_similar_words(
		self, word, max_suggestions=MAX_SPELLING_SUGGESTIONS, min_similarity=MIN_SIMILARITY_THRESHOLD
	):
		"""Find similar words using indexed trigram similarity - much faster!"""
		import difflib

		word = word.lower()
		if len(word) < MIN_WORD_LENGTH:
			return []

		word_trigrams = self._generate_trigrams(word)
		word_length = len(word)

		try:
			# Find candidate words that share trigrams (MUCH faster than checking all words)
			placeholders = ",".join("?" * len(word_trigrams))
			candidates = self.sql(
				f"""
                SELECT t.word, v.frequency, v.length, COUNT(*) as shared_trigrams
                FROM search_trigrams t
                JOIN search_vocabulary v ON t.word = v.word
                WHERE t.trigram IN ({placeholders})
                    AND ABS(v.length - ?) <= ?  -- Length filter for efficiency
                GROUP BY t.word, v.frequency, v.length
                HAVING shared_trigrams >= 1  -- Must share at least 1 trigram
                ORDER BY shared_trigrams DESC, v.frequency DESC
            """,
				(*word_trigrams, word_length, MAX_EDIT_DISTANCE),
				read_only=True,
			)
		except sqlite3.Error:
			return []

		similarities = []
		word_trigram_set = set(word_trigrams)

		for candidate_word, freq, candidate_length, _ in candidates:
			# Quick length-based filter
			if abs(candidate_length - word_length) > MAX_EDIT_DISTANCE:
				continue

			candidate_trigrams = set(self._generate_trigrams(candidate_word))

			# Jaccard similarity for trigrams
			intersection = len(word_trigram_set & candidate_trigrams)
			union = len(word_trigram_set | candidate_trigrams)
			trigram_similarity = intersection / union if union > 0 else 0

			# Skip if trigram similarity is too low
			if trigram_similarity < 0.3:
				continue

			# Sequence similarity for additional accuracy (only for promising candidates)
			seq_similarity = difflib.SequenceMatcher(None, word, candidate_word).ratio()

			# Combined similarity with frequency boost
			combined_similarity = (
				trigram_similarity * SIMILARITY_TRIGRAM_WEIGHT + seq_similarity * SIMILARITY_SEQUENCE_WEIGHT
			)
			frequency_boost = min(
				MAX_FREQUENCY_BOOST, 1.0 + (freq / FREQUENCY_BOOST_FACTOR)
			)  # Slight boost for common words
			final_score = combined_similarity * frequency_boost

			if final_score >= min_similarity:
				similarities.append((candidate_word, final_score))

		# Sort by similarity and return top suggestions
		similarities.sort(key=lambda x: x[1], reverse=True)
		return [word for word, score in similarities[:max_suggestions]]

	def _build_vocabulary(self, documents):
		"""Build vocabulary and trigram index from documents for spelling correction."""
		import re

		word_freq = defaultdict(int)
		word_regex = re.compile(r"\w+")  # Compile regex once for efficiency

		# Extract words from all documents in batches
		for i, doc in enumerate(documents):
			# Show progress for large document sets
			if i % 1000 == 0:
				progress = 80 + int((i / len(documents)) * 15)  # 80-95% range
				self._update_progress(
					f"Processing vocabulary ({i}/{len(documents)})", progress, 100, absolute=True
				)

			# Process title and content together for efficiency
			combined_text = " ".join(
				[(doc.get("title", "") or "").lower(), (doc.get("content", "") or "").lower()]
			)

			# Extract all words at once with compiled regex
			words = word_regex.findall(combined_text)

			for word in words:
				if len(word) > MIN_WORD_LENGTH - 1 and word.isalpha():  # Filter out short words and non-alpha
					word_freq[word] += 1

		# Clear existing data in a single transaction
		conn = self._get_connection()
		try:
			cursor = conn.cursor()
			cursor.execute("DELETE FROM search_vocabulary")
			cursor.execute("DELETE FROM search_trigrams")
			conn.commit()
		finally:
			conn.close()

		if not word_freq:
			return

		# Prepare batch data for vocabulary
		vocab_data = []
		trigram_data = []
		trigram_set = set()  # Use set to avoid duplicate trigrams

		for word, freq in word_freq.items():
			vocab_data.append((word, freq, len(word)))

			# Generate trigrams for this word
			trigrams = self._generate_trigrams(word)
			for trigram in trigrams:
				trigram_key = (trigram, word)
				if trigram_key not in trigram_set:
					trigram_set.add(trigram_key)
					trigram_data.append(trigram_key)

		# Use batch inserts with a single transaction
		conn = self._get_connection()
		try:
			cursor = conn.cursor()

			# Batch insert vocabulary
			cursor.executemany(
				"INSERT INTO search_vocabulary (word, frequency, length) VALUES (?, ?, ?)", vocab_data
			)

			# Batch insert trigrams (duplicates already removed)
			cursor.executemany("INSERT INTO search_trigrams (trigram, word) VALUES (?, ?)", trigram_data)

			conn.commit()
		finally:
			conn.close()

	# Database and Infrastructure Methods

	def _get_connection(self, read_only=False):
		"""Get SQLite connection with FTS5 support and performance optimizations."""
		try:
			conn = sqlite3.connect(self.db_path)
			conn.row_factory = sqlite3.Row

			# Apply performance optimizations
			cursor = conn.cursor()
			self._set_pragmas(cursor, read_only)

			# Test the connection
			cursor.execute("SELECT 1")
			return conn
		except sqlite3.Error as e:
			frappe.log_error(f"Failed to connect to search database: {e}")
			raise SQLiteSearchIndexMissingError(f"Search database connection failed: {e}") from e

	def _set_pragmas(self, cursor, is_read=False):
		"""Set SQLite performance pragmas."""
		cursor.execute("PRAGMA journal_mode = WAL;")  # Write-Ahead Logging for concurrency
		cursor.execute("PRAGMA synchronous = NORMAL;")  # Better performance vs FULL
		cursor.execute("PRAGMA cache_size = -8192;")  # 8MB cache
		cursor.execute("PRAGMA temp_store = MEMORY;")  # Memory temp storage
		if is_read:
			cursor.execute("PRAGMA query_only = 1;")  # Read-only optimization

	def _ensure_fts_table(self):
		"""Create FTS table and related tables if they don't exist."""
		# Get schema from subclass
		text_fields = self.schema["text_fields"]
		metadata_fields = self.schema["metadata_fields"]
		tokenizer = self.schema["tokenizer"]

		# Use a single transaction for all table creation operations
		conn = self._get_connection()
		try:
			cursor = conn.cursor()

			# Create the FTS table with dynamic columns
			cursor.execute(f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS search_fts USING fts5(
                    doc_id UNINDEXED,
                    {", ".join([f"{field}" for field in text_fields])},
                    {", ".join([f"{field} UNINDEXED" for field in metadata_fields])},
                    tokenize="{tokenizer}"
                )
            """)

			# Create the vocabulary and trigram tables
			cursor.execute("""
                CREATE TABLE IF NOT EXISTS search_vocabulary (
                    word TEXT PRIMARY KEY,
                    frequency INTEGER DEFAULT 1,
                    length INTEGER
                )
            """)

			cursor.execute("""
                CREATE TABLE IF NOT EXISTS search_trigrams (
                    trigram TEXT,
                    word TEXT,
                    PRIMARY KEY (trigram, word)
                )
            """)

			# Index for fast trigram lookups
			cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_trigram_lookup ON search_trigrams(trigram)
            """)

			conn.commit()
		finally:
			conn.close()

	def _index_documents(self, documents):
		"""Bulk index documents into SQLite FTS."""
		if not documents:
			return

		# Get schema configuration to build dynamic insert SQL
		text_fields = self.schema["text_fields"]
		metadata_fields = self.schema["metadata_fields"]

		# Always add doc_id as first field (required for FTS)
		all_fields = ["doc_id", *text_fields, *metadata_fields]
		placeholders = ",".join(["?" for _ in all_fields])
		field_names = ",".join(all_fields)

		insert_sql = f"""
            INSERT INTO search_fts ({field_names})
            VALUES ({placeholders})
        """

		# Process documents in chunks to prevent memory issues with large datasets
		chunk_size = 1000
		conn = self._get_connection()
		try:
			cursor = conn.cursor()

			for i in range(0, len(documents), chunk_size):
				chunk = documents[i : i + chunk_size]
				values_to_insert = []

				for doc in chunk:
					# Validate document has required fields
					if not doc.get("doctype") or not doc.get("name"):
						self._warn_invalid_document(doc, "missing doctype/name")
						continue

					# Validate text fields are present
					missing_text_fields = []
					for field in text_fields:
						if field not in doc or doc[field] is None:
							missing_text_fields.append(field)

					if missing_text_fields:
						self._warn_missing_text_fields(
							doc.get("doctype", ""), doc.get("name", ""), missing_text_fields
						)
						continue

					# Build values tuple dynamically based on schema
					values = []
					for field in all_fields:
						# Build doc_id automatically from doctype:name
						if field == "doc_id":
							doc_id = doc.get("id") or f"{doc.get('doctype', '')}:{doc.get('name', '')}"
							values.append(doc_id)
						else:
							values.append(doc.get(field, ""))

					values_to_insert.append(tuple(values))

				# Insert the chunk
				if values_to_insert:
					cursor.executemany(insert_sql, values_to_insert)

			conn.commit()
		finally:
			conn.close()

	def index_doc(self, doctype, docname):
		"""Index a single document."""
		doc = frappe.get_doc(doctype, docname)
		self.raise_if_not_indexed()
		document = self.prepare_document(doc)
		if document:
			self._index_documents([document])

	def remove_doc(self, doctype, docname):
		"""Remove a single document from the index."""
		self.raise_if_not_indexed()
		doc_id = f"{doctype}:{docname}"
		self.sql("DELETE FROM search_fts WHERE doc_id = ?", (doc_id,), commit=True)

	# Utility Methods

	def _update_progress(self, message, progress, total=100, absolute=True):
		"""Update progress bar only if not running in a web request context or tests."""
		if not hasattr(frappe.local, "request") and not frappe.flags.in_test:
			update_progress_bar(message, progress, total, absolute=absolute)

	def _validate_config(self):
		"""Validate document configuration at startup."""
		metadata_fields = self.schema["metadata_fields"]

		for doctype, config in self.doc_configs.items():
			# Validate that all specified fields are present in the 'fields' list
			fields_to_check = ["content_field", "title_field"]
			if "modified" in metadata_fields:
				fields_to_check.append("modified_field")

			for field_key in fields_to_check:
				field_value = config.get(field_key)
				if field_value and field_value not in config["fields"]:
					raise ValueError(
						f"{field_key.replace('_', ' ').title()} '{field_value}' not found in 'fields' list for Doctype '{doctype}'"
					)

	def _empty_search_result(self, title_only=False, filters=None):
		"""Return empty search result structure."""
		return {
			"results": [],
			"summary": {
				"total_matches": 0,
				"filtered_matches": 0,
				"duration": 0,
				"returned_matches": 0,
				"corrected_words": None,
				"corrected_query": None,
				"title_only": title_only,
				"applied_filters": filters or {},
			},
		}

	def _get_db_path(self, is_temp=False):
		"""Get the path for the SQLite FTS database."""
		site_path = frappe.get_site_path()
		db_path = os.path.join(site_path, self.db_name)
		if is_temp:
			return db_path.replace(".db", ".temp.db")
		return db_path

	def _prepare_fts_query(self, query):
		"""Prepare query for FTS5 with proper escaping and operators."""
		query = query.strip()
		if not query:
			return ""

		# Simple query - split into terms and add wildcards for partial matching
		terms = query.split()
		fts_terms = []

		for term in terms:
			# Escape special FTS5 characters
			term = term.replace('"', '""')
			# Add wildcard for prefix matching
			if len(term) > MIN_WORD_LENGTH - 1:
				fts_terms.append(f'"{term}"*')
			else:
				fts_terms.append(f'"{term}"')

		return " ".join(fts_terms)

	def sql(self, query, params=None, read_only=False, commit=False):
		"""Execute a SQL query on the search database."""
		conn = self._get_connection(read_only=read_only)
		try:
			cursor = conn.cursor()
			cursor.execute(query, params or [])

			if read_only:
				return cursor.fetchall()

			if commit:
				conn.commit()

			# For write operations, we might not need to return anything,
			# but returning the cursor could be useful for getting rowcount, etc.
			return cursor
		finally:
			conn.close()

	def prepare_document(self, doc):
		"""Prepare a document for indexing by validating and transforming it."""
		is_valid, config = self._validate_document_for_indexing(doc)
		if not is_valid:
			return None

		document = {
			"id": f"{doc.doctype}:{doc.name}",
			"doctype": doc.doctype,
			"name": doc.name,
		}

		self._add_text_fields_to_document(document, doc, config)
		self._add_metadata_fields_to_document(document, doc, config)

		return document

	def _validate_document_for_indexing(self, doc):
		"""Run all validation checks for a document before indexing."""
		if not hasattr(doc, "doctype") or not doc.doctype:
			self._warn_missing_doctype(doc)
			return False, None

		if not hasattr(doc, "name") or not doc.name:
			self._warn_missing_name(doc.doctype)
			return False, None

		config = self.doc_configs.get(doc.doctype)
		if not config:
			return False, None

		text_fields = self.schema["text_fields"]

		# Validate title field
		if "title" in text_fields:
			title_field = config.get("title_field")
			if title_field and (not hasattr(doc, title_field) or getattr(doc, title_field, None) is None):
				self._warn_missing_title_field(doc.doctype, doc.name, title_field)
				return False, None

		# Validate content field
		if "content" in text_fields:
			content_field = config["content_field"]
			if not hasattr(doc, content_field) or getattr(doc, content_field, None) is None:
				self._warn_missing_content_field(doc.doctype, doc.name, content_field)
				return False, None

		return True, config

	def _add_text_fields_to_document(self, document, doc, config):
		"""Populate text fields in the document for indexing."""
		text_fields = self.schema["text_fields"]
		title_field = config.get("title_field")
		content_field = config["content_field"]

		for field in text_fields:
			if field == "title":
				if title_field:
					raw_title = getattr(doc, title_field, "") or ""
					document["title"] = self._process_content(raw_title)
				else:
					document["title"] = ""  # No title field configured
			elif field == "content":
				raw_content = getattr(doc, content_field, "") or ""
				document["content"] = self._process_content(raw_content)
			else:
				# Handle other custom text fields
				raw_text = getattr(doc, field, "")
				document[field] = self._process_content(raw_text)

	def _add_metadata_fields_to_document(self, document, doc, config):
		"""Populate metadata fields in the document for indexing."""
		metadata_fields = self.schema["metadata_fields"]

		for field in metadata_fields:
			if field in document:  # Skip already populated fields (id, doctype, name)
				continue

			if field == "modified":
				modified_field = config["modified_field"]
				modified_value = getattr(doc, modified_field, None)
				if modified_value:
					if not isinstance(modified_value, datetime.datetime):
						modified_value = frappe.utils.get_datetime(modified_value)
					document["modified"] = modified_value.timestamp()
				continue

			# Handle other metadata fields with potential mapping
			field_mappings = config.get("field_mappings", {})
			actual_field = field_mappings.get(field, field)
			value = getattr(doc, actual_field, None)

			# Convert Mock objects to strings to avoid database errors
			if value is not None and hasattr(value, "_mock_name"):
				value = str(value)

			document[field] = value

	def _process_content(self, content):
		"""Process content to remove HTML tags, links, and images for better indexing quality."""
		if not content:
			return ""

		# Convert to string in case it's a Mock object or other type
		content = str(content)

		soup = BeautifulSoup(content, "html.parser")

		# Extract text content from links before removing HTML tags
		for link in soup.find_all("a"):
			link_text = link.get_text().strip()
			if link_text:
				link.replace_with(link_text)
			else:
				link.replace_with("[link]")

		text = soup.get_text(separator=" ").strip()  # remove tags
		text = re.sub(r"https?://[^\s]+", "[link]", text)  # replace standalone links
		text = re.sub(r"\s+", " ", text).strip()  # normalize whitespace
		return text

	def _generate_trigrams(self, word):
		"""Generate trigrams for a word for fuzzy matching."""
		word = f"  {word.lower()}  "  # Add padding
		return [word[i : i + 3] for i in range(len(word) - 2)]

	def _print_warning_summary(self):
		"""Print a summary of warnings collected during indexing."""
		if not self.warnings:
			return

		print("\n" + "=" * 60)
		print("SEARCH INDEX BUILD WARNINGS")
		print("=" * 60)

		# Group warnings by type
		warning_groups: dict[WarningType, list[IndexWarning]] = {}
		for warning in self.warnings:
			warning_groups.setdefault(warning.type, []).append(warning)

		# Define display names for warning types
		type_display_names = {
			WarningType.INVALID_DOCUMENT: "Invalid Documents",
			WarningType.MISSING_TEXT_FIELDS: "Missing Text Fields",
			WarningType.MISSING_CONTENT_FIELD: "Missing Content Field",
			WarningType.MISSING_TITLE_FIELD: "Missing Title Field",
			WarningType.MISSING_DOCTYPE: "Missing Document Type",
			WarningType.MISSING_NAME: "Missing Document Name",
			WarningType.OTHER: "Other Issues",
		}

		# Print grouped warnings
		for warning_type, warnings in warning_groups.items():
			display_name = type_display_names.get(warning_type, warning_type.value.title())
			print(f"\n{display_name} ({len(warnings)} warnings):")
			print("-" * 50)

			for warning in warnings[:5]:  # Show first 5 warnings of each type
				print(f"  • {warning.message}")

			if len(warnings) > 5:
				print(f"  ... and {len(warnings) - 5} more")

		print(f"\nTotal warnings: {len(self.warnings)}")
		print("=" * 60)

	# Warning helper methods (utility functions)

	def _add_warning(self, warning_type: WarningType, message: str, **kwargs):
		"""Add a structured warning to the warnings list."""
		warning = IndexWarning(type=warning_type, message=message, **kwargs)
		self.warnings.append(warning)

	def _warn_invalid_document(self, doc: dict, reason: str):
		"""Add warning for invalid document."""
		self._add_warning(
			WarningType.INVALID_DOCUMENT,
			f"Skipping document with {reason}: {doc}",
			doctype=doc.get("doctype"),
			docname=doc.get("name"),
		)

	def _warn_missing_text_fields(self, doctype: str, docname: str, missing_fields: list):
		"""Add warning for missing text fields."""
		self._add_warning(
			WarningType.MISSING_TEXT_FIELDS,
			f"Document {doctype}:{docname} missing text fields: {missing_fields}",
			doctype=doctype,
			docname=docname,
			missing_fields=missing_fields,
		)

	def _warn_missing_content_field(self, doctype: str, docname: str, field: str):
		"""Add warning for missing content field."""
		self._add_warning(
			WarningType.MISSING_CONTENT_FIELD,
			f"Document {doctype}:{docname} missing content field '{field}'",
			doctype=doctype,
			docname=docname,
			field=field,
		)

	def _warn_missing_title_field(self, doctype: str, docname: str, field: str):
		"""Add warning for missing title field."""
		self._add_warning(
			WarningType.MISSING_TITLE_FIELD,
			f"Document {doctype}:{docname} missing title field '{field}'",
			doctype=doctype,
			docname=docname,
			field=field,
		)

	def _warn_missing_doctype(self, doc: Any):
		"""Add warning for missing doctype."""
		self._add_warning(
			WarningType.MISSING_DOCTYPE,
			f"Document missing doctype: {doc}",
			docname=getattr(doc, "name", None),
		)

	def _warn_missing_name(self, doctype: str):
		"""Add warning for missing name."""
		self._add_warning(WarningType.MISSING_NAME, f"Document missing name: {doctype}", doctype=doctype)

	def get_warning_statistics(self) -> dict[str, Any]:
		"""Get warning statistics for programmatic use."""
		if not self.warnings:
			return {"total": 0, "by_type": {}}

		stats = {"total": len(self.warnings), "by_type": {}}

		for warning in self.warnings:
			warning_type = warning.type.value
			if warning_type not in stats["by_type"]:
				stats["by_type"][warning_type] = {"count": 0, "examples": []}

			stats["by_type"][warning_type]["count"] += 1

			# Keep a few examples
			if len(stats["by_type"][warning_type]["examples"]) < 3:
				stats["by_type"][warning_type]["examples"].append(
					{
						"message": warning.message,
						"doctype": warning.doctype,
						"docname": warning.docname,
						"field": warning.field,
						"missing_fields": warning.missing_fields,
					}
				)

		return stats


# Module-level Functions for background tasks


def build_index_if_not_exists():
	"""Build index if it doesn't exist."""
	search_classes = get_search_classes()

	for SearchClass in search_classes:
		build_index(SearchClass, force=False)


def build_index(
	SearchClass: type[SQLiteSearch] | None = None, search_class_path: str | None = None, force: bool = False
):
	"""Build search index for SearchClass"""
	if not SearchClass and not search_class_path:
		raise ValueError("Either SearchClass or search_class_path must be provided")

	if search_class_path:
		SearchClass = frappe.get_attr(search_class_path)

	search = SearchClass()
	if not search.is_search_enabled():
		return
	if not search.index_exists() or force:
		print(f"{SearchClass.__name__}: Index does not exist, building...")
		search.build_index()


def build_index_in_background():
	"""Enqueue index building in background."""
	search_classes = get_search_classes()
	for SearchClass in search_classes:
		search = SearchClass()
		if not search.is_search_enabled():
			return
		search_class_path = f"{SearchClass.__module__}.{SearchClass.__name__}"
		print(f"Enqueuing {search_class_path}.build_index")
		frappe.enqueue(
			"frappe.search.sqlite_search.build_index",
			queue="long",
			job_id=search_class_path,
			deduplicate=True,
			# build_index args
			search_class_path=search_class_path,
			force=True,
		)


def update_doc_index(doc: Document, method=None):
	search_classes = get_search_classes()

	for SearchClass in search_classes:
		search = SearchClass()

		if not (search.is_search_enabled() and search.index_exists()):
			return

		for doctype, config in search.doc_configs.items():
			if doc.doctype == doctype:
				fields = config.get("fields", [])
				if not fields:
					continue

				any_field_changed = any(doc.has_value_changed(field) for field in fields)
				if any_field_changed:
					print(f"Enqueuing {search.__class__.__name__}.index_doc for {doc.doctype}:{doc.name}")
					search.index_doc(doctype, doc.name)


def delete_doc_index(doc: Document, method=None):
	search_classes = get_search_classes()

	for SearchClass in search_classes:
		search = SearchClass()

		if not (search.is_search_enabled() and search.index_exists()):
			return

		for doctype, config in search.doc_configs.items():
			if doc.doctype == doctype:
				fields = config.get("fields", [])
				if not fields:
					continue

				print(f"Enqueuing {search.__class__.__name__}.remove_doc for {doc.doctype}:{doc.name}")
				search.remove_doc(doctype, doc.name)


def get_search_classes() -> list[type[SQLiteSearch]]:
	module_paths = frappe.get_hooks("sqlite_search")
	search_classes = [frappe.get_attr(path) for path in module_paths]

	for search_class in search_classes:
		# validate if search classes extend from SQLiteSearch
		if not issubclass(search_class, SQLiteSearch):
			raise TypeError(f"Search class {search_class.__name__} must extend SQLiteSearch")

	return search_classes
