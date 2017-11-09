# imports - module imports
import frappe

@frappe.whitelist()
def get(user = None):
	user  = user or frappe.session.user 
	duser = frappe.get_doc('User', user)

	droom = frappe.get_list('Chat Room',
		fields  = ["type", "name", "room_name"],
		filters = [['Chat Room User', 'user', '=', user]]
	)

	res   = dict(
		status = duser.chat_status,
		rooms  = droom
	)

	return res

@frappe.whitelist()
def set_status(status, user = None):
	user = user or frappe.session.user
	doc  = frappe.get_doc('User', user)

	if doc.chat_status != status:
		doc.update(dict(
			chat_status = status
		))
		doc.save()

		users = frappe.get_all('User')
		pub_users = [u for u in users if u.name != user]

		for pub_user in pub_users:
			# TODO: Check if user currently holds a session.
			response = dict(
				user = doc.name,
				first_name = doc.first_name,
				status = doc.chat_status
			)
			frappe.publish_realtime('chat:user:status', response, user = pub_user.name)