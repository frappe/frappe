// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Connected App', {
	refresh: frm => {
		frm.add_custom_button(__("Get OpenID Configuration"), async () => {
			if(!frm.doc.openid_configuration) {
				frappe.msgprint(__('Please enter OpenID Configuration URL'));
			} else {
				try {
					const response = await fetch(frm.doc.openid_configuration);
					const oidc = await response.json();
					frm.set_value('authorization_endpoint', oidc.authorization_endpoint);
					frm.set_value('token_endpoint', oidc.token_endpoint);
					frm.set_value('userinfo_endpoint', oidc.userinfo_endpoint);
					frm.set_value('introspection_endpoint', oidc.introspection_endpoint);
					frm.set_value('revocation_endpoint', oidc.revocation_endpoint);
				} catch(error) {
					frappe.msgprint(__('Please check OpenID Configuration URL'));
				}
			}
		});

		frm.add_custom_button(__("Init"), async () => {
			frappe.call({
				method: "initiate_auth_code_flow",
				doc: frm.doc,
				callback: function(r) {
                    window.location.replace(r.message);
				}
			})
		});
	}
});
