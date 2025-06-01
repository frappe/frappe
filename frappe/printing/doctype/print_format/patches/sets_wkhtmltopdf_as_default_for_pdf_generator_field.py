import nts


def execute():
	"""sets "wkhtmltopdf" as default for pdf_generator field"""
	for pf in nts.get_all("Print Format", pluck="name"):
		nts.db.set_value("Print Format", pf, "pdf_generator", "wkhtmltopdf", update_modified=False)
