import json

import nts


def execute():
	"""Handle introduction of UI tours"""
	completed = {}
	for tour in nts.get_all("Form Tour", {"ui_tour": 1}, pluck="name"):
		completed[tour] = {"is_complete": True}

	User = nts.qb.DocType("User")
	nts.qb.update(User).set("onboarding_status", json.dumps(completed)).run()
