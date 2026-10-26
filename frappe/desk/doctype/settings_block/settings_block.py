# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class SettingsBlock(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		anchors: DF.Code | None
		binding_type: DF.Literal["", "Single", "Record"]
		bindings: DF.Code | None
		component: DF.Data | None
		description: DF.SmallText | None
		document_type: DF.Link | None
		fields: DF.Code | None
		key: DF.Data
		label: DF.Data | None
		name_resolver: DF.Literal["", "session_user"]
		pane: DF.Data
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		save_mode: DF.Literal["auto", "button"]
		settings: DF.Code | None
	# end: auto-generated types

	_DOCTYPE_NAME = "Settings Block"
