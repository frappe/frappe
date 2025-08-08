// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Connected App", {
	refresh: (frm) => {
		frm.add_custom_button(__("Get OpenID Configuration"), async () => {
			frm.call("get_openid_configuration").then(({ message: oidc }) => {
				frm.set_value("authorization_uri", oidc.authorization_endpoint);
				frm.set_value("token_uri", oidc.token_endpoint);
				frm.set_value("userinfo_uri", oidc.userinfo_endpoint);
				frm.set_value("introspection_uri", oidc.introspection_endpoint);
				frm.set_value("revocation_uri", oidc.revocation_endpoint);

				frm.fields_dict.authorization_uri.section.collapse(false); // Un-collapse
				frappe.show_alert(__("OpenID Configuration fetched successfully!"));
			});
		});

		if (!frm.is_new()) {
			frm.add_custom_button(__("Connect to {}", [frm.doc.provider_name]), async () => {
				frappe.call({
					method: "initiate_web_application_flow",
					doc: frm.doc,
					callback: (r) => {
						window.open(r.message, "_blank");
					},
				});
			});
		}

		frm.toggle_display("sb_client_credentials_section", !frm.is_new());
	},
});
