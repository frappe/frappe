nts.listview_settings["Webhook Request Log"] = {
	onload: function (list_view) {
		nts.require("logtypes.bundle.js", () => {
			nts.utils.logtypes.show_log_retention_message(list_view.doctype);
		});
	},
};
