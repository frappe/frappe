import re

import nts
from nts.query_builder import DocType


def execute():
	"""Replace temporarily available Database Aggregate APIs on nts (develop)

	APIs changed:
	        * nts.db.max => nts.qb.max
	        * nts.db.min => nts.qb.min
	        * nts.db.sum => nts.qb.sum
	        * nts.db.avg => nts.qb.avg
	"""
	ServerScript = DocType("Server Script")
	server_scripts = (
		nts.qb.from_(ServerScript)
		.where(
			ServerScript.script.like("%nts.db.max(%")
			| ServerScript.script.like("%nts.db.min(%")
			| ServerScript.script.like("%nts.db.sum(%")
			| ServerScript.script.like("%nts.db.avg(%")
		)
		.select("name", "script")
		.run(as_dict=True)
	)

	for server_script in server_scripts:
		name, script = server_script["name"], server_script["script"]

		for agg in ["avg", "max", "min", "sum"]:
			script = re.sub(f"nts.db.{agg}\\(", f"nts.qb.{agg}(", script)

		nts.db.set_value("Server Script", name, "script", script)
