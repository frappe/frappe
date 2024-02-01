import frappe


def execute():
	user = frappe.qb.DocType("User")
	role_profiles = frappe.qb.from_(user).select(user.name, user.role_profile_name).run(as_dict=True)
	for user in role_profiles:
		if not user.role_profile_name:
			continue
		user = frappe.get_doc("User", user.name)
		new_role_profiles = []
		new_role_profiles.append({"role_profile": user.role_profile_name})
		user.update({"role_profile_name": new_role_profiles})
		user.save()
