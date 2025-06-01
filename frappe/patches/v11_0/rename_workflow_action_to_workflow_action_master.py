import nts
from nts.model.rename_doc import rename_doc


def execute():
	if nts.db.table_exists("Workflow Action") and not nts.db.table_exists("Workflow Action Master"):
		rename_doc("DocType", "Workflow Action", "Workflow Action Master")
		nts.reload_doc("workflow", "doctype", "workflow_action_master")
