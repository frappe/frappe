frappe.listview_settings["Recorder Request"] = {
	hide_name_column: true,

	onload(listview) {
		listview.page.sidebar.remove();
		if (!has_common(frappe.user_roles, ["Administrator", "System Manager"])) return;

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
			if (!listview.recorder_enabled) return;

			const route = frappe.get_route() || [];
			if (route[0] != "List" || "Recorder Request" != route[1]) {
				return;
			}

			listview.refresh();
		}, 5000);
	},

	refresh(listview) {
		this.setup_recorder_controls(listview);
		this.update_indicators(listview);
	},

	setup_recorder_controls(listview) {
		frappe.xcall("frappe.recorder.status").then((status) => {
			if (status) {
				listview.recorder_enabled = true;
				listview.page.set_primary_action(__("Stop"), () => {
					frappe.call({
						method: "frappe.recorder.stop",
						callback: function () {
							listview.refresh();
						},
					});
				});
			} else {
				listview.recorder_enabled = false;
				listview.page.set_primary_action(__("Start"), () => {
					frappe.call({
						method: "frappe.recorder.start",
						callback: function () {
							listview.refresh();
						},
					});
				});
			}
		});
	},

	update_indicators(listview) {
		if (listview.recorder_enabled) {
			listview.page.set_indicator(__("Active"), "green");
		} else {
			listview.page.set_indicator(__("Inactive"), "red");
		}
	},
};
