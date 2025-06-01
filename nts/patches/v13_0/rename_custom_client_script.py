import nts
from nts.model.rename_doc import rename_doc


def execute():
	if nts.db.exists("DocType", "Client Script"):
		return

	nts.flags.ignore_route_conflict_validation = True
	rename_doc("DocType", "Custom Script", "Client Script")
	nts.flags.ignore_route_conflict_validation = False

	nts.reload_doctype("Client Script", force=True)
