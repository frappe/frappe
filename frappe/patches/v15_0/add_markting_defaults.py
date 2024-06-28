from frappe.desk.page.setup_wizard.install_fixtures import update_marketing_medium, update_marketing_sources


def execute():
	"""Seed default Markting Sources and Media."""
	update_marketing_medium()
	update_marketing_sources()
