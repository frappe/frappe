import frappe

def execute():
	"""
		in communication move feedback details to content
		remove Guest None from sender full name
		setup feedback request trigger's is_manual field
	"""
	frappe.reload_doc('core', 'doctype', 'dynamic_link')
	frappe.reload_doc('email', 'doctype', 'contact')
	
	frappe.reload_doc("core", "doctype", "feedback_request")
	frappe.reload_doc("core", "doctype", "communication")
	
	if frappe.db.has_column('Communication', 'feedback'):
		frappe.db.sql("""update tabCommunication set content=ifnull(feedback, "feedback details not provided")
			where communication_type="Feedback" and content is NULL""")

	frappe.db.sql(""" update tabCommunication set sender_full_name="" where communication_type="Feedback"
		and sender_full_name='Guest None' """)

	frappe.db.sql(""" update `tabFeedback Request` set is_manual=1, feedback_trigger="Manual"
		where ifnull(feedback_trigger, '')='' """)