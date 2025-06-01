import json

import nts


def execute():
	if nts.db.exists("Social Login Key", "github"):
		nts.db.set_value(
			"Social Login Key", "github", "auth_url_data", json.dumps({"scope": "user:email"})
		)
