# Copyright (c) 2022, nts Technologies and Contributors
# See license.txt

import nts
from nts.core.doctype.rq_worker.rq_worker import RQWorker
from nts.tests.utils import ntsTestCase


class TestRQWorker(ntsTestCase):
	def test_get_worker_list(self):
		workers = RQWorker.get_list({})
		self.assertGreaterEqual(len(workers), 1)
		self.assertTrue(any("short" in w.queue_type for w in workers))

	def test_worker_serialization(self):
		workers = RQWorker.get_list({})
		nts.get_doc("RQ Worker", workers[0].name)
