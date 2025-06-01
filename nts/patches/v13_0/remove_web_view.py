import nts


def execute():
	nts.delete_doc_if_exists("DocType", "Web View")
	nts.delete_doc_if_exists("DocType", "Web View Component")
	nts.delete_doc_if_exists("DocType", "CSS Class")
