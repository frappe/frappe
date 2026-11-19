# /desk-architecture: the desk's layers, flows and layer breaks, built from the working tree.

import json
import os
import re
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
		return self.build_response(with_translations(build_diagram()), 200)


def build_diagram() -> str:
	"""The page, built by the script from the code as it is on disk."""
	repo = os.path.dirname(frappe.get_app_path("frappe"))
	# Exit code 1 only means the code breaks layers.json; the page still shows it.
	try:
		run = subprocess.run(
			["node", os.path.join(repo, SCRIPT), "--stdout"],
			cwd=repo,
			capture_output=True,
			text=True,
			timeout=60,
		)
	except (OSError, subprocess.TimeoutExpired) as e:
		not_built(str(e))
	if not run.stdout:
		not_built(run.stderr)
	return run.stdout


def not_built(reason: str):
	frappe.throw(f"<pre>{frappe.utils.escape_html(reason)}</pre>", title=frappe._("Diagram Not Built"))


def with_translations(page: str) -> str:
	"""The page with the translations of its own `__()` strings in the user's language."""
	translations = frappe.translate.get_all_translations(frappe.local.lang)
	# Prettier may break the line after "__(", and quotes a label that holds " with '.
	literals = re.findall(r"""__\(\s*(["'])((?:(?!\1)[^\\]|\\.)*)\1""", page)
	texts = {re.sub(r"\\(.)", r"\1", text) for _quote, text in literals}
	messages = {text: translations[text] for text in texts if text in translations}
	return page.replace("/*MESSAGES*/{}", json.dumps(messages).replace("<", "\\u003c"), 1)
