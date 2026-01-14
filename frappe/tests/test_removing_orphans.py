import frappe
from frappe.model.sync import remove_orphan_entities
from frappe.modules.export_file import delete_folder
from frappe.tests import IntegrationTestCase


class TestRemovingOrphans(IntegrationTestCase):
	def test_removing_orphan(self):
		_before = frappe.conf.developer_mode
		frappe.conf.developer_mode = True
		# Create a new report
		report = frappe.new_doc("Report")
		args = {
			"doctype": "Report",
			"report_name": "Orphan Report",
			"ref_doctype": "DocType",
			"is_standard": "Yes",
			"module": "Custom",
		}
		report.update(args)
		report.save()
		print(f"Created report: {report.name}")
		# delete only fixture (emulating that the export/entity is deleted by the developer)
		delete_folder("Custom", "Report", report.name)
		self.assertTrue(frappe.db.exists("Report", report.name))
		if frappe.db.exists("Report", report.name):
			remove_orphan_entities()
		self.assertFalse(frappe.db.exists("Report", report.name))
		frappe.conf.developer_mode = _before
