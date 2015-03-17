email_defaults = {
	"GMail": {
		"pop3_server": "pop.gmail.com",
		"use_ssl": 1,
		"enable_outgoing": 1,
		"smtp_server": "smtp.gmail.com",
		"smtp_port": 587,
		"use_tls": 1
	},
	"Outlook.com": {
		"pop3_server": "pop3.live.com",
		"use_ssl": 1,
		"enable_outgoing": 1,
		"smtp_server": "smtp.live.com",
		"smtp_port": 587,
		"use_tls": 1
	},
	"Yahoo Mail": {
		"pop3_server": "pop.mail.yahoo.com ",
		"use_ssl": 1,
		"enable_outgoing": 1,
		"smtp_server": "smtp.mail.yahoo.com",
		"smtp_port": 465,
		"use_tls": 1
	},
};

frappe.ui.form.on("Email Account", "service", function(frm) {
	if(frm.doc.service && email_defaults[frm.doc.service]) {
		$.each(email_defaults[frm.doc.service], function(key, value) {
			frm.set_value(key, value);
		})
	}
});

frappe.ui.form.on("Email Account", "email_id", function(frm) {
	if(!frm.doc.email_account_name) {
		frm.set_value("email_account_name",
			(frm.doc.service ? frm.doc.service + " " : "")
			+ toTitle(frm.doc.email_id.split("@")[0].replace(/[._]/g, " ")));
	}
});

