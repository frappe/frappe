nts.listview_settings["Integration Request"] = {
	onload: function (list_view) {
		nts.require("logtypes.bundle.js", () => {
			nts.utils.logtypes.show_log_retention_message(list_view.doctype);
		});
	},
};
