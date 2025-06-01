import nts


def execute():
	nts.reload_doc("workflow", "doctype", "workflow_transition")
	nts.db.sql("update `tabWorkflow Transition` set allow_self_approval=1")
