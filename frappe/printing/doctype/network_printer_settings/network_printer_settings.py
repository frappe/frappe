# Copyright (c) 2021, nts Technologies and contributors
# For license information, please see license.txt

import nts
from nts import _
from nts.model.document import Document


class NetworkPrinterSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from nts.types import DF

		port: DF.Int
		printer_name: DF.Literal[None]
		server_ip: DF.Data

	# end: auto-generated types
	@nts.whitelist()
	def get_printers_list(self, ip="127.0.0.1", port=631):
		printer_list = []
		try:
			import cups
		except ImportError:
			nts.throw(
				_(
					"""This feature can not be used as dependencies are missing.
				Please contact your system manager to enable this by installing pycups!"""
				)
			)
			return
		try:
			cups.setServer(self.server_ip)
			cups.setPort(self.port)
			conn = cups.Connection()
			printers = conn.getPrinters()
			printer_list.extend(
				{"value": printer_id, "label": printer["printer-make-and-model"]}
				for printer_id, printer in printers.items()
			)
		except RuntimeError:
			nts.throw(_("Failed to connect to server"))
		except nts.ValidationError:
			nts.throw(_("Failed to connect to server"))
		return printer_list


@nts.whitelist()
def get_network_printer_settings():
	return nts.db.get_list("Network Printer Settings", pluck="name")
