import nts


def execute():
	nts.reload_doc("core", "doctype", "user")
	nts.db.sql(
		"""
		UPDATE `tabUser`
		SET `home_settings` = ''
		WHERE `user_type` = 'System User'
	"""
	)
