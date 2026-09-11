# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from flow.utils.system_generated import block_delete, block_rename, validate_immutable

MAX_DESCRIPTION_LENGTH = 1024


class FlowSkill(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		description: DF.SmallText
		enabled: DF.Check
		instructions: DF.LongText
		is_system_generated: DF.Check
		title: DF.Data
	# end: auto-generated types

	def validate(self):
		self._validate_description()
		validate_immutable(self, ("description", "instructions"))

	def on_trash(self):
		block_delete(self)

	def before_rename(self, old: str, new: str, merge: bool = False) -> None:
		block_rename(self, old)

	def _validate_description(self):
		"""Every bound skill's description rides in the agent's prompt, so keep it short."""
		if len(self.description or "") > MAX_DESCRIPTION_LENGTH:
			frappe.throw(
				_("Description must be at most {0} characters.").format(MAX_DESCRIPTION_LENGTH),
				title=_("Description Too Long"),
			)
