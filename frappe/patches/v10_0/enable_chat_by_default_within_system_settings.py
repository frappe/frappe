import nts


def execute():
	nts.reload_doctype("System Settings")
	doc = nts.get_single("System Settings")
	doc.enable_chat = 1

	# Changes prescribed by Nabin Hait (nabin@nts.io)
	doc.flags.ignore_mandatory = True
	doc.flags.ignore_permissions = True

	doc.save()
