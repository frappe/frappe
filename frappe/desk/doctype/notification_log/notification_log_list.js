nts.listview_settings["Notification Log"] = {
	onload: function (listview) {
		nts.require("logtypes.bundle.js", () => {
			nts.utils.logtypes.show_log_retention_message(cur_list.doctype);
		});
	},
};
