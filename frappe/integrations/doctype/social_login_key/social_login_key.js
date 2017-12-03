// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt
const fields = [
	"provider_name", "base_url", "custom_base_url", "icon_type",
	"icon", "authorize_url", "access_token_url", "redirect_url",
	"api_endpoint", "api_endpoint_args", "auth_url_data"
];

frappe.ui.form.on('Social Login Key', {
	refresh(frm) {
		setup_fields(frm);
	},

	social_login_provider(frm) {
		if(frm.doc.social_login_provider != "Custom"){
			frappe.call({
				"doc": frm.doc,
				"method": "get_social_login_provider",
				"args": {
					"provider": frm.doc.social_login_provider
				}
			}).done((r)=>{
				const provider = r.message;
				for(var field of Object.keys(frm.fields_dict)){
					if (fields.includes(field)) {
						frm.set_value(field, provider[field]);
						frm.set_df_property(field, "read_only", 1);
					}
				}
			});
		} else {
			for(var field of Object.keys(frm.fields_dict)){
				if (fields.includes(field)) {
					frm.set_value(field, "");
					frm.set_df_property(field, "read_only", 0);
					setup_fields(frm);
				}
			}
		}
	},

	custom_base_url(frm) {
		setup_fields(frm);
	}
});

function setup_fields(frm) {
	for(var f of fields){
		if(frm.doc.social_login_provider == "Custom"){
			frm.set_value("custom_base_url", 1);
			frm.set_df_property("custom_base_url", "read_only", 1);
		}
		if(frm.doc.social_login_provider != "Custom")
			frm.set_df_property(f, "read_only", 1);
		if(frm.doc.custom_base_url)
			frm.set_df_property("base_url", "read_only", 0);
	}
}
