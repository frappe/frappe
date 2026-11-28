"""Flow Skills the current user may read, for API clients and agents."""

import frappe
from frappe import _


def list_skills() -> dict:
	"""The enabled skills the current user may read. Empty, not an error, without access."""
	if not frappe.has_permission("Flow Skill", "read"):
		return {"skills": []}
	skills = frappe.get_list(
		"Flow Skill",
		filters={"enabled": 1},
		fields=["name", "description"],
		order_by="name asc",
	)
	return {"skills": skills}


def get_skill(name: str, file: str | None = None) -> dict:
	"""A skill's instructions, or with `file`, a file from its app folder. A folder path lists
	the files in it."""
	from frappe.flow.doctype.flow_skill.flow_skill import skill_file

	skill = frappe.read_doc("Flow Skill", name)
	# System Managers read disabled skills too, so the permission check does not exclude them.
	if not skill.enabled:
		raise frappe.DoesNotExistError(_("{0} {1} not found").format(_("Flow Skill"), name))
	if file:
		return {"name": skill.name, "file": file, "content": skill_file(skill.name, file)}
	return {"name": skill.name, "description": skill.description, "instructions": skill.instructions}
