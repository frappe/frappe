frappe.listview_settings["Newsletter"] = {
	add_fields: ["subject", "email_sent", "schedule_sending"],
	get_indicator: function (doc) {
		if (doc.email_sent) {
<<<<<<< HEAD
			return [__("Sent"), "green", "email_sent,=,Yes"];
		} else if (doc.schedule_sending) {
			return [__("Scheduled"), "purple", "email_sent,=,No|schedule_sending,=,Yes"];
		} else {
			return [__("Not Sent"), "gray", "email_sent,=,No"];
=======
			return [__("Sent"), "green", "email_sent,=,1"];
		} else if (doc.schedule_sending) {
			return [__("Scheduled"), "purple", "email_sent,=,0|schedule_sending,=,1"];
		} else {
			return [__("Not Sent"), "gray", "email_sent,=,0"];
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
		}
	},
};
