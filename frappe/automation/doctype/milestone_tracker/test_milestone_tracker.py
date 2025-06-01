# Copyright (c) 2019, nts Technologies and Contributors
# License: MIT. See LICENSE
import nts
import nts.cache_manager
from nts.tests.utils import ntsTestCase


class TestMilestoneTracker(ntsTestCase):
	def test_milestone(self):
		nts.db.delete("Milestone Tracker")

		nts.cache.delete_key("milestone_tracker_map")

		milestone_tracker = nts.get_doc(
			dict(doctype="Milestone Tracker", document_type="ToDo", track_field="status")
		).insert()

		todo = nts.get_doc(dict(doctype="ToDo", description="test milestone", status="Open")).insert()

		milestones = nts.get_all(
			"Milestone",
			fields=["track_field", "value", "milestone_tracker"],
			filters=dict(reference_type=todo.doctype, reference_name=todo.name),
		)

		self.assertEqual(len(milestones), 1)
		self.assertEqual(milestones[0].track_field, "status")
		self.assertEqual(milestones[0].value, "Open")

		todo.status = "Closed"
		todo.save()

		milestones = nts.get_all(
			"Milestone",
			fields=["track_field", "value", "milestone_tracker"],
			filters=dict(reference_type=todo.doctype, reference_name=todo.name),
			order_by="modified desc",
		)

		self.assertEqual(len(milestones), 2)
		self.assertEqual(milestones[0].track_field, "status")
		self.assertEqual(milestones[0].value, "Closed")

		# cleanup
		nts.db.delete("Milestone")
		milestone_tracker.delete()
