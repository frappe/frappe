nts.listview_settings["Route History"] = {
	onload: function (listview) {
		nts.require("logtypes.bundle.js", () => {
			nts.utils.logtypes.show_log_retention_message(cur_list.doctype);
		});
	},
};
