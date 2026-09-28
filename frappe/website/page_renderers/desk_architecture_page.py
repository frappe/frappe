# /desk-architecture: the desk's layers, flows and layer breaks, built from the working tree.

import os
import shutil
import subprocess

import frappe
from frappe.website.page_renderers.base_renderer import BaseRenderer

ROUTE = "desk-architecture"
SCRIPT = "frontend/architecture/diagram.mjs"


class DeskArchitecturePage(BaseRenderer):
	def can_render(self):
		return self.path == ROUTE and bool(frappe.conf.developer_mode)

	def render(self):
		frappe.local.no_cache = 1
		if frappe.session.user == "Guest":
			frappe.local.flags.redirect_location = f"/login?redirect-to=/{ROUTE}"
			raise frappe.Redirect
		frappe.only_for("System Manager")
		return self.build_response(build_diagram(), 200)


def build_diagram() -> str:
	"""The page, built by the script from the code as it is on disk."""
	repo = os.path.dirname(frappe.get_app_path("frappe"))
	# Exit code 1 only means the code breaks layers.json; the page still shows it.
	run = subprocess.run(
		[shutil.which("node") or "node", os.path.join(repo, SCRIPT), "--stdout"],
		cwd=repo,
		capture_output=True,
		text=True,
		timeout=60,
	)
	if not run.stdout:
		frappe.throw(
			f"<pre>{frappe.utils.escape_html(run.stderr)}</pre>", title=frappe._("Diagram Not Built")
		)
	return run.stdout
