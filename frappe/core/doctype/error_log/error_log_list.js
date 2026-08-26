frappe.listview_settings["Error Log"] = {
	add_fields: ["seen"],
	get_indicator: function (doc) {
		if (cint(doc.seen)) {
			return [__("Seen"), "green", "seen,=,1"];
		} else {
			return [__("Not Seen"), "red", "seen,=,0"];
		}
	},
	order_by: "creation desc",
	onload: function (listview) {
		const update_queued_error_logs = () => {
			return frappe
				.xcall("frappe.core.doctype.error_log.error_log.get_queued_error_log_count")
				.then((count) => {
					if (!count) {
						listview.page.clear_indicator();
						return;
					}

					const indicator_label =
						count === 1
							? __("1 Queued Error Log")
							: __("{0} Queued Error Logs", [count]);
					listview.page.set_indicator(indicator_label, "orange");
					listview.page.add_menu_item(__("Flush Error Logs"), () => {
						return frappe
							.xcall("frappe.core.doctype.error_log.error_log.flush_error_logs")
							.then(() => {
								frappe.show_alert(__("Queued Error Logs flushed"));
								listview.refresh();
								return update_queued_error_logs();
							});
					});
				});
		};

		update_queued_error_logs();

		listview.page.add_menu_item(__("Clear Error Logs"), function () {
			frappe.call({
				method: "frappe.core.doctype.error_log.error_log.clear_error_logs",
				callback: function () {
					listview.refresh();
				},
			});
		});

		frappe.require("logtypes.bundle.js", () => {
			frappe.utils.logtypes.show_log_retention_message(cur_list.doctype);
		});
	},
};
