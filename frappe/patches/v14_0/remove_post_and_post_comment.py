import nts


def execute():
	nts.delete_doc_if_exists("DocType", "Post")
	nts.delete_doc_if_exists("DocType", "Post Comment")
