# Copyright (c) 2020, Frappe Technologies and contributors
# License: MIT. See LICENSE

from collections import defaultdict

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.modules.export_file import export_to_files


class ModuleOnboarding(Document):
	_DOCTYPE_NAME = "Module Onboarding"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.desk.doctype.onboarding_permission.onboarding_permission import OnboardingPermission
		from frappe.desk.doctype.onboarding_step_map.onboarding_step_map import OnboardingStepMap
		from frappe.types import DF

		allow_roles: DF.TableMultiSelect[OnboardingPermission]
		is_complete: DF.Check
		module: DF.Link
		steps: DF.Table[OnboardingStepMap]
		title: DF.Data
	# end: auto-generated types

	def on_update(self):
		if frappe.conf.developer_mode:
			export_to_files(record_list=[["Module Onboarding", self.name]], record_module=self.module)

			for step in self.steps:
				export_to_files(record_list=[["Onboarding Step", step.step]], record_module=self.module)

	def get_steps(self):
		return [frappe.get_doc("Onboarding Step", step.step) for step in self.steps]

	def get_allowed_roles(self):
		all_roles = [role.role for role in self.allow_roles]
		if "System Manager" not in all_roles:
			all_roles.append("System Manager")

		return all_roles

	def check_completion(self):
		if self.is_complete:
			return True

		steps = self.get_steps()
		is_complete = [bool(step.is_complete or step.is_skipped) for step in steps]
		if all(is_complete):
			self.is_complete = True
			frappe.enqueue(self.mark_as_completed, enqueue_after_commit=True)
			return True

		return False

	def mark_as_completed(self):
		self.is_complete = True
		self.save(ignore_permissions=True)

	@frappe.whitelist()
	def reset_progress(self):
		self.db_set("is_complete", 0)

		for step in self.get_steps():
			step.db_set("is_complete", 0)
			step.db_set("is_skipped", 0)

		frappe.msgprint(_("Module onboarding progress reset"), alert=True)

	def before_export(self, doc):
		doc.is_complete = 0

	def reset_onboarding(self):
		frappe.only_for("Administrator")

		self.is_complete = 0
		steps = self.get_steps()
		for step in steps:
			step.is_complete = 0
			step.is_skipped = 0
			step.save()

		self.save()


# The role every onboarding is visible to, whatever it lists. This mirrors `get_allowed_roles`:
# the two are the same rule read from opposite ends, one document at a time and the whole site at
# once, and must stay in step.
IMPLICIT_ROLE = "System Manager"


def get_permitted_onboardings() -> dict[str, str]:
	"""Return the onboarding each module offers this user, keyed by module.

	This replaces the `Sidebar.module_onboarding` pointer. A stored pointer names one onboarding
	regardless of who is looking, so it either bypassed the role check the onboarding declares or
	showed a panel that then refused to load. Asking which onboardings the user's roles allow
	answers both questions, per user.

	A module may have more than one, because `Module Onboarding` is named by prompt rather than by
	module, so the choice has to be deterministic instead of whichever row the database returned
	first. It picks the earliest-created onboarding this user is allowed. Creation order is stable
	across sites and re-imports, so an app adding a second onboarding does not move everyone off
	the one they were working through.

	This checks roles only. Whether the onboarding is finished, and whether the site enables
	onboarding at all, stay with `get_onboarding_data`, which loads it. A module that offers an
	onboarding you may see does not stop offering it once you complete it.
	"""
	onboardings = frappe.get_all("Module Onboarding", fields=["name", "module"], order_by="creation asc")
	if not onboardings:
		return {}

	roles = set(frappe.get_roles())
	allowed_by_name = defaultdict(set)
	for row in frappe.get_all(
		"Onboarding Permission",
		filters={"parenttype": "Module Onboarding", "parent": ["in", [o.name for o in onboardings]]},
		fields=["parent", "role"],
	):
		allowed_by_name[row.parent].add(row.role)

	permitted = {}
	for onboarding in onboardings:
		if not onboarding.module or onboarding.module in permitted:
			continue
		if roles & (allowed_by_name[onboarding.name] | {IMPLICIT_ROLE}):
			permitted[onboarding.module] = onboarding.name

	return permitted
