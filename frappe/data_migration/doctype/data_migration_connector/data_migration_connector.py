# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
import psycopg2

class DataMigrationConnector(Document):
	def connect(self):
		self.connection = PostGresConnection(self.as_dict())

	def get_objects(self, object_type, condition=None):
		return self.connection.get_objects(object_type, condition)

class PostGresConnection(object):
	def __init__(self, properties):
		self.__dict__.update(properties)
		self._connector = psycopg2.connect("host='{0}' dbname='{1}' user='{2}' password='{3}'".format(self.hostname,
				self.database_name, self.username, self.password))
		self.cursor = self._connector.cursor()

	def get_objects(self, object_type, condition):
		if not condition:
			condition = ''
		else:
			condition = ' WHERE ' + condition
		self.cursor.execute('SELECT * FROM {0}{1}'.format(object_type, condition))
		raw_data = self.cursor.fetchall()
		data = []
		for r in raw_data:
			row_dict = frappe._dict({})
			for i in range(len(r)):
				row_dict[self.cursor.description[i][0]] = r[i]
			data.append(row_dict)

		return data
