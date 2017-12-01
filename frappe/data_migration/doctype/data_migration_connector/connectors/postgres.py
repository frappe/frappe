from __future__ import unicode_literals
import frappe, psycopg2
from .base import BaseConnection

class PostGresConnection(BaseConnection):
	def __init__(self, properties):
		self.__dict__.update(properties)
		self._connector = psycopg2.connect("host='{0}' dbname='{1}' user='{2}' password='{3}'".format(self.hostname,
				self.database_name, self.username, self.password))
		self.cursor = self._connector.cursor()

	def get_objects(self, object_type, condition, selection):
		if not condition:
			condition = ''
		else:
			condition = ' WHERE ' + condition
		self.cursor.execute('SELECT {0} FROM {1}{2}'.format(selection, object_type, condition))
		raw_data = self.cursor.fetchall()
		data = []
		for r in raw_data:
			row_dict = frappe._dict({})
			for i, value in enumerate(r):
				row_dict[self.cursor.description[i][0]] = value
			data.append(row_dict)

		return data

	def get_join_objects(self, object_type, field, primary_key):
		"""
		field.formula 's first line will be list of tables that needs to be linked to fetch an item
		The subsequent lines that follows will contain one to one mapping across tables keys
		"""
		condition = ""
		key_mapping = field.formula.split('\n')
		obj_type = key_mapping[0]
		selection = field.source_fieldname

		for d in key_mapping[1:]:
			condition += d + ' AND '

		condition += str(object_type) + ".id=" + str(primary_key)

		return self.get_objects(obj_type, condition, selection)
