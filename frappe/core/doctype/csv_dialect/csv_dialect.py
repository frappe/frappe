# -*- coding: utf-8 -*-
# Copyright (c) 2019, ALYF.de ERPNext Consulting and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import msgprint, _
import csv
import json
import six
from six import StringIO, string_types
from frappe.utils import encode, cstr, cint, flt, comma_or


class CSVDialect(Document):
	def to_csv(self, data):
		if not self.write_header:
			data = data[1:]

		writer = UnicodeWriter(dialect=self)
		for row in data:
			writer.writerow(row)

		return writer.getvalue()


class UnicodeWriter:
	def __init__(self, dialect):
		register_dialect(dialect)
		self.encoding = dialect.encoding or 'utf-8'
		self.queue = StringIO()
		self.writer = csv.writer(self.queue, dialect.name)

	def writerow(self, row):
		if six.PY2:
			row = encode(row, self.encoding)
		self.writer.writerow(row)

	def getvalue(self):
		return self.queue.getvalue()

def register_dialect(dialect):
	"""
	register a new csv dialect named dialect.name
	"""
	quoting = {
		'None': csv.QUOTE_NONE,
		'Minimal': csv.QUOTE_MINIMAL,
		'Non-numeric': csv.QUOTE_NONNUMERIC,
		'All': csv.QUOTE_ALL
	}
	args = {
		'delimiter': dialect.delimiter.encode('utf-8') or b',',
		'quoting': quoting[dialect.quoting] or csv.QUOTE_MINIMAL,
		'doublequote': bool(dialect.doublequote),
		'quotechar': dialect.quote_character.encode('utf-8') or b'"',
		'lineterminator': b'\n' if dialect.line_terminator is 'Unix' else b'\r\n'
	}

	if ((args['quoting'] is csv.QUOTE_NONE) or (not args['doublequote'])):
		args['escapechar'] = dialect.escape_character.encode('utf-8')

	csv.register_dialect(dialect.name, **args)


@frappe.whitelist()
def send_csv_to_client(args):
	"""
	/api/method/frappe.utils.csvutils.send_csv_to_client?args={"data":[],"filename":"","dialect":""}

	args: {
		"data": [ [], [], ... ],        # list of rows
		"filename": "",                 # any name for the output file
		"dialect": "" 					# name of a `CSV Dialect`
	}
	"""
	if isinstance(args, string_types):
		args = json.loads(args)

	args = frappe._dict(args)
	dialect = frappe.get_doc('CSV Dialect', args.dialect)

	frappe.response["result"] = dialect.to_csv(args.data)
	frappe.response["doctype"] = args.filename
	frappe.response["type"] = "csv"
