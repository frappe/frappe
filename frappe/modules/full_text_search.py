# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import os
from whoosh.index import create_in, open_dir
from whoosh.fields import TEXT, ID, Schema


def build_index(index_name, documents):
	schema = Schema(title=TEXT(stored=True), path=ID(stored=True), content=TEXT)

	index_dir = os.path.join(frappe.utils.get_bench_path(), "indexes", index_name)
	frappe.create_folder(index_dir)

	ix = create_in(index_dir, schema)
	writer = ix.writer()

	for document in documents:
		writer.add_document(
			title=document.title, path=document.path, content=document.content
		)

	writer.commit()


def search(index_name, text):
	from whoosh.qparser import QueryParser

	index_dir = os.path.join(frappe.utils.get_bench_path(), "indexes", index_name)
	ix = open_dir(index_dir)

	with ix.searcher() as searcher:
		query = QueryParser("content", ix.schema).parse(text)
		results = searcher.search(query)

	return results
