# Copyright (c) 2015, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import nts
from nts.tests.utils import ntsTestCase
from nts.utils.data import add_to_date, today


class TestDocumentLocks(ntsTestCase):
	def test_locking(self):
		todo = nts.get_doc(dict(doctype="ToDo", description="test")).insert()
		todo_1 = nts.get_doc("ToDo", todo.name)

		todo.lock()
		self.assertRaises(nts.DocumentLockedError, todo_1.lock)
		todo.unlock()

		todo_1.lock()
		self.assertRaises(nts.DocumentLockedError, todo.lock)
		todo_1.unlock()

	def test_operations_on_locked_documents(self):
		todo = nts.get_doc(dict(doctype="ToDo", description="testing operations")).insert()
		todo.lock()

		with self.assertRaises(nts.DocumentLockedError):
			todo.description = "Random"
			todo.save()

		# Checking for persistant locks across all instances.
		doc = nts.get_doc("ToDo", todo.name)
		self.assertEqual(doc.is_locked, True)

		with self.assertRaises(nts.DocumentLockedError):
			doc.description = "Random"
			doc.save()

		doc.unlock()
		self.assertEqual(doc.is_locked, False)
		self.assertEqual(todo.is_locked, False)

	def test_locks_auto_expiry(self):
		todo = nts.get_doc(dict(doctype="ToDo", description=nts.generate_hash())).insert()
		todo.lock()

		self.assertRaises(nts.DocumentLockedError, todo.lock)

		with self.freeze_time(add_to_date(today(), days=3)):
			todo.lock()
