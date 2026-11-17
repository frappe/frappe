import os
import shutil

import frappe


def execute():
	"""Move Flow's vector store out of private/files."""
	old = frappe.get_site_path("private", "files", "lancedb")
	if not os.path.isdir(old):
		return
	new = frappe.get_site_path("private", "lancedb")
	if os.path.exists(new):
		# made by new code before this patch ran, so the old store is the real one
		shutil.rmtree(new)
	shutil.move(old, new)
