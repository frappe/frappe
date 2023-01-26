# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from whoosh.fields import ID, TEXT, Schema
from whoosh.index import EmptyIndexError, create_in, open_dir
from whoosh.qparser import FieldsPlugin, MultifieldParser, WildcardPlugin
from whoosh.query import FuzzyTerm, Prefix
from whoosh.writing import AsyncWriter

import frappe
from frappe.utils import update_progress_bar


class FullTextSearch:
	"""Frappe Wrapper for Whoosh"""

	def __init__(self, index_name):
		self.index_name = index_name
		self.index_path = get_index_path(index_name)
		self.schema = self.get_schema()
		self.id = self.get_id()

	def get_schema(self):
		return Schema(name=ID(stored=True), content=TEXT(stored=True))

	def get_fields_to_search(self):
		return ["name", "content"]

	def get_id(self):
		return "name"

	def get_items_to_index(self):
		"""Get all documents to be indexed conforming to the schema"""
		return []

	def get_document_to_index(self):
		return {}

	def build(self):
		"""Build search index for all documents"""
		self.documents = self.get_items_to_index()
		self.build_index()

	def update_index_by_name(self, doc_name):
		"""Wraps `update_index` method, gets the document from name
		and updates the index. This function changes the current user
		and should only be run as administrator or in a background job.

		Args:
		        self (object): FullTextSearch Instance
		        doc_name (str): name of the document to be updated
		"""
		document = self.get_document_to_index(doc_name)
		if document:
			self.update_index(document)

	def remove_document_from_index(self, doc_name):
		"""Remove document from search index

		Args:
		        self (object): FullTextSearch Instance
		        doc_name (str): name of the document to be removed
		"""
		if not doc_name:
			return

		ix = self.get_index()
		with ix.searcher():
			writer = AsyncWriter(ix)
			writer.delete_by_term(self.id, doc_name)
			writer.commit(optimize=True)

	def update_index(self, document):
		"""Update search index for a document

		Args:
		        self (object): FullTextSearch Instance
		        document (_dict): A dictionary with title, path and content
		"""
		ix = self.get_index()

		with ix.searcher():
			writer = AsyncWriter(ix)
			writer.delete_by_term(self.id, document[self.id])
			writer.add_document(**document)
			writer.commit(optimize=True)

	def get_index(self):
		try:
			return open_dir(self.index_path)
		except EmptyIndexError:
			return self.create_index()

	def create_index(self):
		frappe.create_folder(self.index_path)
		return create_in(self.index_path, self.schema)

	def build_index(self):
		"""Build index for all parsed documents"""
		ix = self.create_index()
		writer = AsyncWriter(ix)

		for i, document in enumerate(self.documents):
			if document:
				writer.add_document(**document)
			update_progress_bar("Building Index", i, len(self.documents))

		writer.commit(optimize=True)

	def search(self, text, scope=None, limit=20):
		"""Search from the current index

		Args:
		        text (str): String to search for
		        scope (str, optional): Scope to limit the search. Defaults to None.
		        limit (int, optional): Limit number of search results. Defaults to 20.

		Returns:
		        [List(_dict)]: Search results
		"""
		ix = self.get_index()

		results = None
		out = []

		search_fields = self.get_fields_to_search()
		fieldboosts = {}

		# apply reducing boost on fields based on order. 1.0, 0.5, 0.33 and so on
		for idx, field in enumerate(search_fields, start=1):
			fieldboosts[field] = 1.0 / idx

		with ix.searcher() as searcher:
			parser = MultifieldParser(
				search_fields, ix.schema, termclass=FuzzyTermExtended, fieldboosts=fieldboosts
			)
			parser.remove_plugin_class(FieldsPlugin)
			parser.remove_plugin_class(WildcardPlugin)
			query = parser.parse(text)

			filter_scoped = None
			if scope:
				filter_scoped = Prefix(self.id, scope)
			results = searcher.search(query, limit=limit, filter=filter_scoped)

			for r in results:
				out.append(self.parse_result(r))

		return out


class FuzzyTermExtended(FuzzyTerm):
	def __init__(self, fieldname, text, boost=1.0, maxdist=2, prefixlength=1, constantscore=True):
		super().__init__(
			fieldname,
			text,
			boost=boost,
			maxdist=maxdist,
			prefixlength=prefixlength,
			constantscore=constantscore,
		)


def get_index_path(index_name):
	return frappe.get_site_path("indexes", index_name)
