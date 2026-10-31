import re

import frappe
from frappe.flow.assistant.assistant import ASSISTANT_AGENT_TITLE
from frappe.flow.lib.agent import _with_sub_agents
from frappe.model.rename_doc import rename_doc


def execute():
	"""Name the agents, skills and tools that apps and Flow ship `<app>/<name>`, after freeing that
	form from the site's own agents and skills."""
	for doctype in ("Flow Agent", "Flow Skill"):
		for name in frappe.get_all(
			doctype, {"is_system_generated": 0, "name": ["like", "%/%"]}, pluck="name"
		):
			new = base = name.replace("/", "-")
			count = 1
			while frappe.db.exists(doctype, new):
				count += 1
				new = f"{base}-{count}"
			_rename(doctype, name, new)

	# `__` is how the model calls app tools: crm__read_records
	for name in frappe.get_all("Flow Tool", {"is_system_generated": 0}, pluck="name"):
		if "__" in name:
			new = base = re.sub(r"_+", "_", name)
			count = 1
			while frappe.db.exists("Flow Tool", new):
				count += 1
				new = f"{base}_{count}"
			_rename("Flow Tool", name, new)

	# rows named `<app>/...` already have their new name
	for skill in frappe.get_all(
		"Flow Skill", {"is_system_generated": 1, "name": ["not like", "%/%"]}, ["name", "app", "title"]
	):
		if skill.app:
			_rename("Flow Skill", skill.name, f"{skill.app}/{skill.title}")

	for tool in frappe.get_all(
		"Flow Tool",
		{"is_system_generated": 1, "type": "Imported", "name": ["not like", "%/%"]},
		["name", "import_path", "slug"],
	):
		_rename("Flow Tool", tool.name, f"{tool.import_path.split('.', 1)[0]}/{tool.slug}")

	apps = {}
	for path in frappe.get_hooks("flow_agents"):
		try:
			agents = frappe.get_attr(path)()
		except frappe.ValidationError:
			continue  # sync_agents logs it
		for agent in agents:
			for item in _with_sub_agents(agent):
				apps.setdefault(item.name.split("/", 1)[1], set()).add(item.app)
	apps[ASSISTANT_AGENT_TITLE] = {"frappe"}
	for name in frappe.get_all(
		"Flow Agent", {"is_system_generated": 1, "name": ["in", list(apps)]}, pluck="name"
	):
		# declared by two apps: either could own the row, so leave it
		if len(apps[name]) > 1:
			continue
		[app] = apps[name]
		if _rename("Flow Agent", name, f"{app}/{name}"):
			frappe.db.set_value("Flow Agent", f"{app}/{name}", "app", app, update_modified=False)


def _rename(doctype: str, old: str, new: str) -> bool:
	if old == new or frappe.db.exists(doctype, new):
		return False
	# without validate, as before_rename refuses system-generated rows
	rename_doc(doctype, old, new, force=True, validate=False, show_alert=False, rebuild_search=False)
	return True
