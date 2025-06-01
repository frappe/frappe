import nts


def execute():
	nts.db.sql(
		"""
		UPDATE tabFile
		SET folder = 'Home/Attachments'
		WHERE ifnull(attached_to_doctype, '') != ''
		AND folder = 'Home'
	"""
	)
