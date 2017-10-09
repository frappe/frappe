from six import with_metaclass
from abc import ABCMeta, abstractmethod
from frappe.utils.password import get_decrypted_password

class BaseConnection(with_metaclass(ABCMeta)):

	@abstractmethod
	def get(self):
		pass

	@abstractmethod
	def insert(self):
		pass

	@abstractmethod
	def update(self):
		pass

	@abstractmethod
	def delete(self):
		pass

	def get_password(self):
		return get_decrypted_password('Data Migration Connector', self.connector.name)