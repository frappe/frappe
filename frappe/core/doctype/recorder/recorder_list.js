frappe.listview_settings["Recorder"] = {
	hide_name_column: true,

	onload(listview) {
		listview.page.sidebar.remove();
		if (!has_common(frappe.user_roles, ["Administrator", "System Manager"])) return;

		if (listview.list_view_settings) {
			listview.list_view_settings.disable_comment_count = true;
		}

		listview.page.add_button(__("Clear"), () => {
			frappe.call({
				method: "frappe.recorder.delete",
				callback: function () {
					listview.refresh();
				},
			});
		});

		listview.page.add_menu_item(__("Import"), () => {
			new frappe.ui.FileUploader({
				folder: this.current_folder,
				on_success: (file) => {
					if (cur_list.data.length > 0) {
						// don't replace existing capture
						return;
					}
					frappe.call({
						method: "frappe.recorder.import_data",
						args: {
							file: file.file_url,
						},
						callback: function () {
							listview.refresh();
						},
					});
				},
			});
		});

		listview.page.add_menu_item(__("Export"), () => {
			frappe.call({
				method: "frappe.recorder.export_data",
				callback: function (r) {
					const data = r.message;
					const filename = `${data[0]["uuid"]}..${data[data.length - 1]["uuid"]}.json`;

					const el = document.createElement("a");
					el.setAttribute(
						"href",
						"data:application/json," + encodeURIComponent(JSON.stringify(data))
					);
					el.setAttribute("download", filename);
					el.click();
				},
			});
		});

		setInterval(() => {
			if (listview.list_view_settings.disable_auto_refresh) {
				return;
			}
			if (!listview.enabled) return;

			const route = frappe.get_route() || [];
			if (route[0] != "List" || "Recorder" != route[1]) {
				return;
			}

			listview.refresh();
		}, 5000);
	},

	refresh(listview) {
		this.fetch_recorder_status(listview).then(() => this.refresh_controls(listview));
	},

	refresh_controls(listview) {
		this.setup_recorder_controls(listview);
		this.update_indicators(listview);
	},

	fetch_recorder_status(listview) {
		return frappe.xcall("frappe.recorder.status").then((status) => {
			listview.enabled = Boolean(status);
		});
	},

	setup_recorder_controls(listview) {
		listview.page.set_primary_action(listview.enabled ? __("Stop") : __("Start"), () => {
			frappe.call({
				method: listview.enabled ? "frappe.recorder.stop" : "frappe.recorder.start",
				callback: function () {
					listview.refresh();
				},
			});
			listview.enabled = !listview.enabled;
			this.refresh_controls(listview);
		});
	},

	update_indicators(listview) {
		if (listview.enabled) {
			listview.page.set_indicator(__("Active"), "green");
		} else {
			listview.page.set_indicator(__("Inactive"), "red");
		}
	},
};
