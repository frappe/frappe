import nts


def execute():
	doctype = "Integration Request"

	if not nts.db.has_column(doctype, "integration_type"):
		return

	nts.db.set_value(
		doctype,
		{"integration_type": "Remote", "integration_request_service": ("!=", "PayPal")},
		"is_remote_request",
		1,
	)
	nts.db.set_value(
		doctype,
		{"integration_type": "Subscription Notification"},
		"request_description",
		"Subscription Notification",
	)
