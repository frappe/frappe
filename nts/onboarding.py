import json

import nts


@nts.whitelist()
def get_onboarding_status():
	onboarding_status = nts.db.get_value("User", nts.session.user, "onboarding_status")
	return nts.parse_json(onboarding_status) if onboarding_status else {}


@nts.whitelist()
def update_user_onboarding_status(steps: str, appName: str):
	steps = json.loads(steps)

	# get the current onboarding status
	onboarding_status = nts.db.get_value("User", nts.session.user, "onboarding_status")
	onboarding_status = nts.parse_json(onboarding_status)

	# update the onboarding status
	onboarding_status[appName + "_onboarding_status"] = steps

	nts.db.set_value(
		"User", nts.session.user, "onboarding_status", json.dumps(onboarding_status), update_modified=False
	)
