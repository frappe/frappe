import os
import shutil

import frappe
from frappe.flow.knowledge.ingest import enqueue_ingestion


def execute():
	"""Drop the old LanceDB store and re-embed every knowledge source."""
	old = frappe.get_site_path("private", "lancedb")
	if not os.path.isdir(old):
		return
	shutil.rmtree(old, ignore_errors=True)
	sources = frappe.get_all("Flow Knowledge Source", pluck="name")
	try:
		for source in sources:
			enqueue_ingestion(source, rebuild=True)
	except Exception:
		# queue is down: the daily sync re-embeds them
		frappe.log_error(title="Flow knowledge re-embed not queued")
