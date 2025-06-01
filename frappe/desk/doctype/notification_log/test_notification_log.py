# Copyright (c) 2019, nts Technologies and Contributors
# License: MIT. See LICENSE
import nts
from nts.core.doctype.user.user import get_system_users
from nts.desk.form.assign_to import add as assign_task
from nts.tests.utils import ntsTestCase


class TestNotificationLog(ntsTestCase):
	def test_assignment(self):
		todo = get_todo()
		user = get_user()

		assign_task(
			{"assign_to": [user], "doctype": "ToDo", "name": todo.name, "description": todo.description}
		)
		log_type = nts.db.get_value(
			"Notification Log", {"document_type": "ToDo", "document_name": todo.name}, "type"
		)
		self.assertEqual(log_type, "Assignment")

	def test_share(self):
		todo = get_todo()
		user = get_user()

		nts.share.add("ToDo", todo.name, user, notify=1)
		log_type = nts.db.get_value(
			"Notification Log", {"document_type": "ToDo", "document_name": todo.name}, "type"
		)
		self.assertEqual(log_type, "Share")

		email = get_last_email_queue()
		content = f"Subject: {nts.utils.get_fullname(nts.session.user)} shared a document ToDo"
		self.assertTrue(content in email.message)


def get_last_email_queue():
	res = nts.get_all("Email Queue", fields=["message"], order_by="creation desc", limit=1)
	return res[0]


def get_todo():
	if not nts.get_all("ToDo"):
		return nts.get_doc({"doctype": "ToDo", "description": "Test for Notification"}).insert()

	res = nts.get_all("ToDo", limit=1)
	return nts.get_cached_doc("ToDo", res[0].name)


def get_user():
	return get_system_users(limit=1)[0]
