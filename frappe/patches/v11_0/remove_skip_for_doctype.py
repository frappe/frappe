import frappe

# `skip_for_doctype` was a un-normalized way of storing for which
# doctypes the user permission was applicable.
# in this patch, we normalize this into `applicable_for` where
# a new record will be created for each doctype where the user permission
# is applicable
#
# if the user permission is applicable for all doctypes, then only
# one record is created

def execute():
	# frappe.db.sql('delete from `tabUser Permission`')
	# frappe.get_doc({'doctype': 'User Permission', u'_liked_by': None, u'modified_by': u'Administrator', u'name': u'76783e783a', u'parent': None, u'_assign': None, u'_user_tags': None, u'for_value': u'User', u'idx': 0, u'parenttype': None, u'allow': u'DocType', u'user': u'suraj@erpnext.com', u'skip_for_doctype': u'', u'applicable_for': None, u'owner': u'Administrator', u'docstatus': 0, u'_comments': None, u'parentfield': None}).insert()
	# frappe.get_doc({'doctype': 'User Permission', u'_liked_by': None, u'modified_by': u'Administrator', u'name': u'456f1be7c5', u'parent': None, u'_assign': None, u'_user_tags': None, u'for_value': u'DocType', u'idx': 0, u'parenttype': None, u'allow': u'DocType', u'user': u'suraj@erpnext.com', u'skip_for_doctype': u'Activity Log\nAddress\nAuto Repeat\nBulk Update\nCalendar View\nContact\nCustom Field\nCustom Script\nData Migration Mapping\nDesktop Icon\nDocType\nEmail Account\nEmail Domain\nEvent\nFeedback Trigger\nGSuite Templates\nIntegration Request\nList Filter\nNotification\nPayment Gateway\nPrint Format\nProperty Setter\nReport\nSuccess Action\nTag Category\nUser Permission\nVersion\nView log\nWebhook\nWorkflow\nWorkflow Action', u'applicable_for': None, u'owner': u'Administrator', u'docstatus': 0, u'_comments': None, u'parentfield': None}).insert()
	# frappe.get_doc({'doctype': 'User Permission', u'_liked_by': None, u'modified_by': u'Administrator', u'name': u'87e85fb24f', u'parent': None, u'_assign': None, u'_user_tags': None, u'for_value': u'Review', u'idx': 0, u'parenttype': None, u'allow': u'Workflow Action Master', u'user': u'suraj@erpnext.com', u'skip_for_doctype': u'Workflow Action Master', u'applicable_for': None, u'owner': u'Administrator', u'docstatus': 0, u'_comments': None, u'parentfield': None}).insert()
	frappe.reload_doctype('User Permission')
	for user_permission in frappe.get_all('User Permission', fields=['*']):
		if not user_permission.skip_for_doctype: continue
		skip_for_doctype = user_permission.skip_for_doctype.split('\n')
		if skip_for_doctype:
			# only specific doctypes are selected
			# split this into multiple records and delete
			frappe.db.sql('delete from `tabUser Permission` where name=%s', user_permission.name)
			user_permission.name = None
			user_permission.skip_for_doctype = None
			for doctype in skip_for_doctype:
				if doctype:
					new_user_permission = frappe.new_doc('User Permission')
					new_user_permission.update(user_permission)
					new_user_permission.applicable_for = doctype
					new_user_permission.db_insert()