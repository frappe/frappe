from __future__ import unicode_literals
import frappe

def execute():
	frappe.reload_doc("integrations", "doctype", "social_login_keys")
	existing_providers = [
		{
			"name": "google",
			"client_id": frappe.get_value("Social Login Keys", None, "google_client_id"), 
			"client_secret": frappe.get_value("Social Login Keys", None, "google_client_secret")
		}, 
		{
			"name": "facebook",
			"client_id": frappe.get_value("Social Login Keys", None, "facebook_client_id"), 
			"client_secret": frappe.get_value("Social Login Keys", None, "facebook_client_secret")
		}, 
		{
			"name": "github",
			"client_id": frappe.get_value("Social Login Keys", None, "github_client_id"), 
			"client_secret": frappe.get_value("Social Login Keys", None, "github_client_secret"), 
		},
		{
			"name": "frappe",
			"base_url": frappe.get_value("Social Login Keys", None, "frappe_server_url"),
			"client_id": frappe.get_value("Social Login Keys", None, "frappe_client_id"),
			"client_secret": frappe.get_value("Social Login Keys", None, "frappe_client_secret")
		}
	]
	delete_user_fields()

	for key in existing_providers:
		key_doc = frappe.get_doc("Social Login Key", key.get("name"))
		key_doc.client_id = key.client_id
		key_doc.client_secret = key.client_secret
		if key.get("base_url"):
			key_doc.base_url = key.get("base_url")
		key_doc.save()
		frappe.db.commit()

def delete_user_fields():
	fieldnames = [
		"facebook_username", "facebook_userid",
		"github_username", "github_userid",
		"google_username", "google_userid",
		"frappe_userid"
	]
	for f in fieldnames:
		d = frappe.get_all("DocField", {"parent":"User","fieldname":f})
		if d:
			frappe.delete_doc("DocField", d[0].get("name"))
