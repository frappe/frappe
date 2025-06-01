# Copyright (c) 2018, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import nts


def execute():
	signatures = nts.db.get_list("User", {"email_signature": ["!=", ""]}, ["name", "email_signature"])
	nts.reload_doc("core", "doctype", "user")
	for d in signatures:
		signature = d.get("email_signature")
		signature = signature.replace("\n", "<br>")
		signature = "<div>" + signature + "</div>"
		nts.db.set_value("User", d.get("name"), "email_signature", signature)
