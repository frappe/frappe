import frappe

def pre_process(issue):
	return {
		'title': issue.title,
		'body': frappe.utils.to_html(issue.body or ''),
		'state': issue.state.title()
	}