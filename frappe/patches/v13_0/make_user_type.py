import nts
from nts.utils.install import create_user_type


def execute():
	nts.reload_doc("core", "doctype", "role")
	nts.reload_doc("core", "doctype", "user_document_type")
	nts.reload_doc("core", "doctype", "user_type_module")
	nts.reload_doc("core", "doctype", "user_select_document_type")
	nts.reload_doc("core", "doctype", "user_type")

	create_user_type()
