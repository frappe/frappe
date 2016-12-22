frappe.email_defaults = {
	"GMail": {
		"email_server": "pop.gmail.com",
		"use_ssl": 1,
		"smtp_server": "smtp.gmail.com",
		"smtp_port": 587,
		"use_tls": 1
	},
	"Outlook.com": {
		"email_server": "pop3.live.com",
		"use_ssl": 1,
		"smtp_server": "smtp.live.com",
		"smtp_port": 587,
		"use_tls": 1
	},
	"Sendgrid": {
		"smtp_server": "smtp.sendgrid.net",
		"smtp_port": 587,
		"use_tls": 1
	},
	"SparkPost": {
		"smtp_server": "smtp.sparkpostmail.com",
		"smtp_port": 587,
		"use_tls": 1
	},
	"Yahoo Mail": {
		"email_server": "pop.mail.yahoo.com",
		"use_ssl": 1,
		"smtp_server": "smtp.mail.yahoo.com",
		"smtp_port": 465,
		"use_tls": 1
	},
	"Yandex.Mail": {
		"email_server": "pop.yandex.com",
		"use_ssl": 1,
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
		"email_server": "imap.live.com"
	},
	"Yahoo Mail": {
		"email_server": "imap.mail.yahoo.com"
	},
	"Yandex.Mail": {
		"email_server": "imap.yandex.com"
	},

};

frappe.ui.form.on("Email Domain", {
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
    show_gmail_message_for_less_secure_apps: function(frm) {
		if(frm.doc.service==="Gmail") {
			frm.dashboard.set_headline_alert('Gmail will only work if you allow access for less secure \
				apps in Gmail settings. <a target="_blank" \
				href="https://support.google.com/accounts/answer/6010255?hl=en">Read this for details</a>');
		}
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
    email_id:function(frm){
        frm.set_value("domain_name",frm.doc.email_id.split("@")[1])
    },
    refresh:function(frm){
        frm.events.show_gmail_message_for_less_secure_apps(frm);
        if (frm.doc.email_id){frm.set_value("domain_name",frm.doc.email_id.split("@")[1])}
        if (frm.doc.__islocal != 1) {
            route = frappe.get_prev_route()
            if (frappe.route_titles["return to email_account"]){
                delete frappe.route_titles["return to email_account"];
                frappe.set_route(route);
            }
        }
    }
})
