import nts


def execute():
	"""
	Deprecate Feedback Trigger and Rating. This feature was not customizable.
	Now can be achieved via custom Web Forms
	"""
	nts.delete_doc("DocType", "Feedback Trigger")
	nts.delete_doc("DocType", "Feedback Rating")
