import frappe

def execute():
	frappe.reload_doc("core", "doctype", "user", force=True)
	frappe.reload_doc("core", "doctype", "user_social_login", force=True)
	users = frappe.get_all("User", filters=[["username", "not in", ["Guest","Administrator"]]])
	for u in users:
		user = frappe.get_doc("User", u.get("name"))
		save = False

		if user.get("fb_userid") and user.get("fb_username"):
			user.append("social_logins", {
				"provider": "facebook",
				"userid": user.get("fb_userid"),
				"username": user.get("fb_username")
			})
			save = True

		if user.get("frappe_userid"):
			user.append("social_logins", {
				"provider": "frappe",
				"userid": user.get("frappe_userid")
			})
			save = True

		if user.get("github_userid") and user.get("github_username"):
			user.append("social_logins", {
				"provider": "github",
				"userid": user.get("github_userid"),
				"username": user.get("github_username"),
			})
			save = True

		if user.get("google_userid"):
			user.append("social_logins", {
				"provider": "google",
				"userid": user.get("google_userid"),
			})
			save = True

		if save:
			user.save()

	# Create Social Login Key(s) from Social Login Keys
	frappe.reload_doc("integrations", "doctype", "social_login_key", force=True)

	if not frappe.db.exists('DocType', 'Social Login Keys'):
		return

	social_login_keys = frappe.get_doc("Social Login Keys", "Social Login Keys")
	if social_login_keys.get("facebook_client_id") or social_login_keys.get("facebook_client_secret"):
		facebook_login_key = frappe.new_doc("Social Login Key")
		facebook_login_key.get_social_login_provider("Facebook", initialize=True)
		facebook_login_key.social_login_provider = "Facebook"
		facebook_login_key.client_id = social_login_keys.get("facebook_client_id")
		facebook_login_key.client_secret = social_login_keys.get("facebook_client_secret")
		if not (facebook_login_key.client_secret and facebook_login_key.client_id):
			facebook_login_key.enable_social_login = 0
		facebook_login_key.save()

	if social_login_keys.get("frappe_server_url"):
		frappe_login_key = frappe.new_doc("Social Login Key")
		frappe_login_key.get_social_login_provider("Frappe", initialize=True)
		frappe_login_key.social_login_provider = "Frappe"
		frappe_login_key.base_url = social_login_keys.get("frappe_server_url")
		frappe_login_key.client_id = social_login_keys.get("frappe_client_id")
		frappe_login_key.client_secret = social_login_keys.get("frappe_client_secret")
		if not (frappe_login_key.client_secret and frappe_login_key.client_id and frappe_login_key.base_url):
			frappe_login_key.enable_social_login = 0
		frappe_login_key.save()

	if social_login_keys.get("github_client_id") or social_login_keys.get("github_client_secret"):
		github_login_key = frappe.new_doc("Social Login Key")
		github_login_key.get_social_login_provider("GitHub", initialize=True)
		github_login_key.social_login_provider = "GitHub"
		github_login_key.client_id = social_login_keys.get("github_client_id")
		github_login_key.client_secret = social_login_keys.get("github_client_secret")
		if not (github_login_key.client_secret and github_login_key.client_id):
			github_login_key.enable_social_login = 0
		github_login_key.save()

	if social_login_keys.get("google_client_id") or social_login_keys.get("google_client_secret"):
		google_login_key = frappe.new_doc("Social Login Key")
		google_login_key.get_social_login_provider("Google", initialize=True)
		google_login_key.social_login_provider = "Google"
		google_login_key.client_id = social_login_keys.get("google_client_id")
		google_login_key.client_secret = social_login_keys.get("google_client_secret")
		if not (google_login_key.client_secret and google_login_key.client_id):
			google_login_key.enable_social_login = 0
		google_login_key.save()

	frappe.delete_doc("DocType", "Social Login Keys")
