frappe.listview_settings["RQ Job"] = {
	hide_name_column: true,

	onload(listview) {
		if (!has_common(frappe.user_roles, ["Administrator", "System Manager"])) return;

		listview.page.add_inner_button(
			__("Remove Failed Jobs"),
			() => {
				frappe.confirm(__("Are you sure you want to remove all failed jobs?"), () => {
					frappe.xcall("frappe.core.doctype.rq_job.rq_job.remove_failed_jobs");
				});
			},
			__("Actions")
		);

		frappe
			.xcall("frappe.core.doctype.rq_job.rq_job.get_custom_queues", undefined, "GET")
			.then((options) => {
				if (!options.length) return;
				const field = listview.page.fields_dict.queue;
				// the filter rows read the DocField, the quick filter its own copy
				const dfs = new Set([frappe.meta.get_docfield("RQ Job", "queue"), field?.df]);
				for (const df of dfs) {
					if (!df) continue;
					const known = (df.options || "").split("\n");
					df.options = [...known, ...options.filter((o) => !known.includes(o))].join(
						"\n"
					);
				}
				field?.set_options();
			});

		frappe
			.xcall("frappe.utils.scheduler.get_scheduler_status", undefined, "GET")
			.then(({ status }) => {
				if (status === "active") {
					listview.page.set_indicator(__("Scheduler: Active"), "green");
				} else {
					listview.page.set_indicator(__("Scheduler: Inactive"), "red");
					listview.page.add_inner_button(
						__("Enable Scheduler"),
						() => {
							frappe.confirm(
								__("Are you sure you want to re-enable scheduler?"),
								() => {
									frappe
										.xcall("frappe.utils.scheduler.activate_scheduler")
										.then(() => {
											frappe.show_alert(__("Enabled Scheduler"));
										})
										.catch((e) => {
											frappe.show_alert({
												message: __("Failed to enable scheduler: {0}", e),
												indicator: "error",
											});
										});
								}
							);
						},
						__("Actions")
					);
				}
			});

		setInterval(() => {
			if (listview.list_view_settings.disable_auto_refresh) {
				return;
			}

			const route = frappe.get_route() || [];
			if (route[0] != "List" || "RQ Job" != route[1]) {
				return;
			}

			listview.refresh();
		}, 15000);
	},
};
