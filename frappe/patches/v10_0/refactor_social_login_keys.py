
import frappe

def execute():
	frappe.reload_doc("core", "doctype", "user", force=True)
	frappe.reload_doc("core", "doctype", "user_social_login", force=True)

	provider_fieldname_map = {
		"frappe": ["frappe_userid"],
		"facebook": ["fb_userid", "fb_username"],
		"github": ["github_userid", "github_username"],
		"google": ["google_userid"],
	}

	for provider in provider_fieldname_map:
		fields_on_user = [f for f in provider_fieldname_map[provider]] #fb_userid
		fields_in_social_login = [f.split("_")[1] for f in provider_fieldname_map[provider]] #userid

		null_condition = ["`tabUser`.`" + field_on_user + "` is not null" for field_on_user in fields_on_user]
		null_condition = " and ".join(null_condition)

		query = """
			insert into `tabUser Social Login` (provider, {social_login_fields})
			select '{provider}' as provider, {user_fields}
			from `tabUser`
			where `tabUser`.`name` not in ('Guest', 'Administrator')
			and {null_condition};
		""".format(
			user_fields = ", ".join(fields_on_user),
			provider=provider,
			social_login_fields = ", ".join(fields_in_social_login),
			null_condition = null_condition
		)

		frappe.db.sql(query)

	frappe.delete_doc("DocType", "Social Login Keys")
