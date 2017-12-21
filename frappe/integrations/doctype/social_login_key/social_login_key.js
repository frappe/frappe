// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt
const fields = [
	"provider_name", "base_url", "custom_base_url",
	"icon", "authorize_url", "access_token_url", "redirect_url",
	"api_endpoint", "api_endpoint_args", "auth_url_data"
];

frappe.ui.form.on('Social Login Key', {
	refresh(frm) {
		frm.trigger("setup_fields");
	},

	custom_base_url(frm) {
		frm.trigger("setup_fields");
	},

	social_login_provider(frm) {
		if(frm.doc.social_login_provider != "Custom") {
			frappe.call({
				"doc": frm.doc,
				"method": "get_social_login_provider",
				"args": {
					"provider": frm.doc.social_login_provider
				}
			}).done((r) => {
				const provider = r.message;
				for(var field of fields) {
					frm.set_value(field, provider[field]);
					frm.set_df_property(field, "read_only", 1);
					if (frm.doc.custom_base_url) {
						frm.toggle_enable("base_url", 1);
					}
				}
			});
		} else {
			frm.trigger("clear_fields");
			frm.trigger("setup_fields");
		}
	},

	setup_fields(frm) {
		// set custom_base_url to read only for "Custom" provider
		if(frm.doc.social_login_provider == "Custom") {
			frm.set_value("custom_base_url", 1);
			frm.set_df_property("custom_base_url", "read_only", 1);
		}

		// set fields to read only for providers from template
		for(var f of fields) {
			if(frm.doc.social_login_provider != "Custom"){
				frm.set_df_property(f, "read_only", 1);
			}
		}

		// enable base_url for providers with custom_base_url
		if(frm.doc.custom_base_url) {
			frm.set_df_property("base_url", "read_only", 0);
			frm.fields_dict["sb_identity_details"].collapse(false);
		}

		// hide social_login_provider and provider_name for non local
		if(!frm.doc.__islocal &&
			(frm.doc.social_login_provider ||
				frm.doc.provider_name)) {
			frm.set_df_property("social_login_provider", "hidden", 1);
			frm.set_df_property("provider_name", "hidden", 1);
		}
	},

	clear_fields(frm) {
		for(var field of fields){
			frm.set_value(field, "");
			frm.set_df_property(field, "read_only", 0);
		}
	}

});
