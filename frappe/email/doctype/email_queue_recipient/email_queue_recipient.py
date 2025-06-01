# Copyright (c) 2015, nts Technologies and contributors
# License: MIT. See LICENSE

import nts
from nts.model.document import Document


class EmailQueueRecipient(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from nts.types import DF

		error: DF.Code | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		recipient: DF.Data | None
		status: DF.Literal["", "Not Sent", "Sent"]
	# end: auto-generated types
	DOCTYPE = "Email Queue Recipient"

	def is_mail_to_be_sent(self):
		return self.status == "Not Sent"

	def is_mail_sent(self):
		return self.status == "Sent"

	def update_db(self, commit=False, **kwargs):
		nts.db.set_value(self.DOCTYPE, self.name, kwargs)
		if commit:
			nts.db.commit()


def on_doctype_update():
	"""Index required for log clearing, modified is not indexed on child table by default"""
	nts.db.add_index("Email Queue Recipient", ["modified"])
