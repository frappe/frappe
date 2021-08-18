frappe.listview_settings['Newsletter'] = {
	add_fields: ["subject", "email_sent", "schedule_sending"],
	get_indicator: function(doc) {
		if (doc.email_sent) {
			return [__("Sent"), "green", "email_sent,=,Yes"];
		} else if (doc.schedule_sending) {
			return [__("Scheduled"), "orange", "email_sent,=,No|schedule_sending,=,Yes"];
		} else {
			return [__("Not Sent"), "orange", "email_sent,=,No"];
		}
	}
};
