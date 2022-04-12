from __future__ import unicode_literals

from abc import ABCMeta, abstractmethod

from six import with_metaclass

from frappe.utils.password import get_decrypted_password


class BaseConnection(with_metaclass(ABCMeta)):
	@abstractmethod
	def get(self, remote_objectname, fields=None, filters=None, start=0, page_length=10):
		pass

	@abstractmethod
	def insert(self, doctype, doc):
		pass

	@abstractmethod
	def update(self, doctype, doc, migration_id):
		pass

	@abstractmethod
	def delete(self, doctype, migration_id):
		pass

	def get_password(self):
		return get_decrypted_password("Data Migration Connector", self.connector.name)
