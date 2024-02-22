# Copyright (c) 2015, Frappe Technologies and contributors
# License: MIT. See LICENSE

from frappe.model.document import Document


class EmailFlagQueue(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		action: DF.Literal["Read", "Unread"]
		communication: DF.Data | None
		email_account: DF.Data | None
		is_completed: DF.Check
		uid: DF.Data | None
	# end: auto-generated types

	pass
