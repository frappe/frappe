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
		user_fields = [f.split("_")[1] for f in provider_fieldname_map[provider]]

		null_condition = ["`tabUser`.`" + user_field + "` is not null" for user_field in user_fields]
		null_condition = " and ".join(null_condition)

		query = """
			insert into `tabUser Social Login` (provider, {social_login_fields})
			select ('{provider}', {user_fields})
			from `tabUser`
			where `tabUser`.`name` not in ('Guest', 'Administrator')
			and ({null_condition});
		""".format(
			user_fields = ", ".join(provider_fieldname_map[provider]),
			provider=provider,
			social_login_fields = ", ".join(user_fields),
			null_condition = null_condition
		)

		frappe.db.sql(query)

	frappe.delete_doc("DocType", "Social Login Keys")
