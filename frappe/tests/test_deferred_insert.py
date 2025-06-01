import nts
from nts.deferred_insert import deferred_insert, save_to_db
from nts.tests.utils import ntsTestCase


class TestDeferredInsert(ntsTestCase):
	def test_deferred_insert(self):
		route_history = {"route": nts.generate_hash(), "user": "Administrator"}
		deferred_insert("Route History", [route_history])

		save_to_db()
		self.assertTrue(nts.db.exists("Route History", route_history))

		route_history = {"route": nts.generate_hash(), "user": "Administrator"}
		deferred_insert("Route History", [route_history])
		nts.clear_cache()  # deferred_insert cache keys are supposed to be persistent
		save_to_db()
		self.assertTrue(nts.db.exists("Route History", route_history))
