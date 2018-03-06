
import frappe

def execute():

	# Update Social Logins in User

	frappe.reload_doc("core", "doctype", "user", force=True)
	frappe.reload_doc("core", "doctype", "user_social_login", force=True)

	standard_cols = ["name", "creation", "modified", "owner", "modified_by", "parent", "parenttype", "parentfield", "idx"]

	provider_source_cols_map = {
		"frappe": ["frappe_userid"],
		"facebook": ["fb_userid", "fb_username"],
		"github": ["github_userid", "github_username"],
		"google": ["google_userid"],
	}

	idx = 0
	for provider in provider_source_cols_map:
		source_social_login_cols = provider_source_cols_map[provider] #fb_userid
		target_social_login_cols = [f.split("_")[1] for f in provider_source_cols_map[provider]] #userid

		creation_time = frappe.utils.get_datetime_str(frappe.utils.get_datetime())

		source_cols = [
			"'{0}' AS `name`".format(str(frappe.generate_hash(length=10))),
			"'{0}' AS `creation`".format(creation_time),
			"'{0}' AS `modified`".format(creation_time),
			"`tabUser`.`owner`",
			"`tabUser`.`modified_by`",
			"`tabUser`.`name` AS `parent`",
			"'User' AS `parenttype`",
			"'social_logins' AS `parentfield`",
			"{0} AS `idx`".format(idx),
			"'{0}' AS `provider`".format(provider)
		]

		null_check_condition = ["`tabUser`.`" + col + "` IS NOT NULL" for col in source_social_login_cols]
		null_check_condition = " OR ".join(null_check_condition)

		source_cols = source_cols + ["`tabUser`.`" + col + "`" for col in source_social_login_cols]
		target_cols = standard_cols + target_social_login_cols

		query = """
			INSERT INTO `tabUser Social Login` ({target_cols})
			SELECT {source_cols}
			FROM `tabUser`
			WHERE `tabUser`.`name` NOT IN ('Guest', 'Administrator')
			AND {null_check_condition};
		""".format(
			source_cols = ", ".join(source_cols),
			target_cols = "`" + "`, `".join(target_cols) + "`",
			null_check_condition = null_check_condition
		)

		frappe.db.sql(query)
		idx += 1


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