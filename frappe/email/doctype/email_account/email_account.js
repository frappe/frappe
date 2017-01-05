frappe.email_defaults = {
	"GMail": {
		"email_server": "pop.gmail.com",
		"use_ssl": 1,
		"enable_outgoing": 1,
		"smtp_server": "smtp.gmail.com",
		"smtp_port": 587,
		"use_tls": 1
	},
	"Outlook.com": {
		"email_server": "pop3-mail.outlook.com",
		"use_ssl": 1,
		"enable_outgoing": 1,
		"smtp_server": "smtp-mail.outlook.com",
		"smtp_port": 587,
		"use_tls": 1
	},
	"Sendgrid": {
		"enable_outgoing": 0,
		"enable_outgoing": 1,
		"smtp_server": "smtp.sendgrid.net",
		"smtp_port": 587,
		"use_tls": 1
	},
	"SparkPost": {
		"enable_incoming": 0,
		"enable_outgoing": 1,
		"smtp_server": "smtp.sparkpostmail.com",
		"smtp_port": 587,
		"use_tls": 1
	},
	"Yahoo Mail": {
		"email_server": "pop.mail.yahoo.com",
		"use_ssl": 1,
		"enable_outgoing": 1,
		"smtp_server": "smtp.mail.yahoo.com",
		"smtp_port": 465,
		"use_tls": 1
	},
	"Yandex.Mail": {
		"email_server": "pop.yandex.com",
		"use_ssl": 1,
		"enable_outgoing": 1,
		"smtp_server": "smtp.yandex.com",
		"smtp_port": 587,
		"use_tls": 1
	},
};

frappe.email_defaults_imap = {
	"GMail": {
		"email_server": "imap.gmail.com"
	},
	"Outlook.com": {
		"email_server": "imap-mail.outlook.com"
	},
	"Yahoo Mail": {
		"email_server": "imap.mail.yahoo.com"
	},
	"Yandex.Mail": {
		"email_server": "imap.yandex.com"
	},

};

frappe.ui.form.on("Email Account", {
	service: function(frm) {
		console.log(frm.doc.service, frappe.email_defaults[frm.doc.service])
		$.each(frappe.email_defaults[frm.doc.service], function(key, value) {
			frm.set_value(key, value);
		})
		if (frm.doc.use_imap) {
			$.each(frappe.email_defaults_imap[frm.doc.service], function(key, value) {
				frm.set_value(key, value);
			});
		}
		frm.events.show_gmail_message_for_less_secure_apps(frm);
	},
	use_imap: function(frm) {
		if (frm.doc.use_imap) {
			$.each(frappe.email_defaults_imap[frm.doc.service], function(key, value) {
				frm.set_value(key, value);
			});
		}
		else{
			$.each(frappe.email_defaults[frm.doc.service], function(key, value) {
				frm.set_value(key, value);
			});
		}
	},
	enable_incoming: function(frm) {
		frm.doc.no_remaining = null //perform full sync
		//frm.set_df_property("append_to", "reqd", frm.doc.enable_incoming);
	},
	notify_if_unreplied: function(frm) {
		frm.set_df_property("send_notification_to", "reqd", frm.doc.notify_if_unreplied);
	},
	onload: function(frm) {
		frm.set_df_property("append_to", "only_select", true);
		frm.set_query("append_to", "frappe.email.doctype.email_account.email_account.get_append_to");
	},
	validate:function(frm){
		frm.events.update_domain(frm,true);
	},
	refresh: function(frm) {
		frm.events.update_domain(frm,true);
		frm.events.enable_incoming(frm);
		frm.events.notify_if_unreplied(frm);
		frm.events.show_gmail_message_for_less_secure_apps(frm);
		if (frm.doc.__islocal != 1) {
			if (frappe.route_titles["create user account"]) {
				var user =frappe.route_titles["create user account"];
				delete frappe.route_titles["create user account"];
				var userdoc = frappe.get_doc("User",user);
				frappe.model.with_doc("User", user, function (doc) { 
					var new_row = frappe.model.add_child(userdoc, "User Email", "user_email");
					new_row.email_account = cur_frm.doc.name;
					new_row.awaiting_password = cur_frm.doc.awaiting_password;
					new_row.email_id = cur_frm.doc.email_id;
					new_row.idx = 0;
					frappe.route_titles["unsaved"] = 1;
					frappe.set_route("Form", "User",user);
				});
            }
        }
	},
	show_gmail_message_for_less_secure_apps: function(frm) {
		if(frm.doc.service==="Gmail") {
			frm.dashboard.set_headline_alert('Gmail will only work if you allow access for less secure \
				apps in Gmail settings. <a target="_blank" \
				href="https://support.google.com/accounts/answer/6010255?hl=en">Read this for details</a>');
		}
	},
	email_id:function(frm){
		//pull domain and if no matching domain go create one
		frm.events.update_domain(frm,false);
	},
	update_domain:function(frm,norefresh){
		if (cur_frm.doc.email_id && !cur_frm.doc.service) {
			frappe.call({
				method: 'get_domain',
				doc: cur_frm.doc,
				async:false,
				args: {
					"email_id": cur_frm.doc.email_id
				},
				callback: function (frm) {
					try {
						if (cur_frm.doc.domain !=frm["message"][0]["name"]) {
							cur_frm.doc.domain = frm["message"][0]["name"]
							cur_frm.doc.email_server= frm["message"][0]["email_server"];
							cur_frm.doc.use_imap= frm["message"][0]["use_imap"];
							cur_frm.doc.smtp_server= frm["message"][0]["smtp_server"];
							cur_frm.doc.use_ssl= frm["message"][0]["use_ssl"];
							cur_frm.doc.use_tls= frm["message"][0]["use_tls"];
							cur_frm.doc.smtp_port = frm["message"][0]["smtp_port"];
							if (!norefresh) {
								cur_frm.refresh();
							}
						}
					}
					catch (Exception) {
						frappe.confirm(
							'Email Domain not configured for this account\nCreate one?',
							function () {
								frappe.model.with_doctype("Email Domain", function() {
									frappe.route_options = {email_id: cur_frm.doc.email_id};
									frappe.route_titles["return to email_account"] = 1
									var doc = frappe.model.get_new_doc("Email Domain");
									frappe.set_route("Form", "Email Domain", doc.name);
								})
							}
						)
					}
				}
			});
		}
	}
});