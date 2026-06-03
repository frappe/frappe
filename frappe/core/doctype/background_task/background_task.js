frappe.ui.form.on("Background Task", {
	refresh(frm) {
		frm.disable_save();

		if (frm.task_update_handler) {
			frappe.realtime.off("task_update", frm.task_update_handler);
			frm.task_update_handler = null;
		}

		if (["Failed", "Cancelled"].includes(frm.doc.status)) {
			if (frm.doc.allow_user_retry) {
				frm.add_custom_button(__("Retry Task"), () => {
					frappe.call({
						method: "frappe.core.doctype.background_task.background_task.retry_task",
						args: { task_id: frm.doc.task_id },
						callback: () => {
							frm.reload_doc();
						},
					});
				})
					.removeClass("btn-default")
					.addClass("btn-primary");
			}
			return;
		}

		if (!["Queued", "Running"].includes(frm.doc.status)) {
			return;
		}

		let stage_text = frm.doc.stage || "";
		if (frm.doc.status === "Queued") {
			stage_text = __("Waiting for a worker to pick up this task...");
		}
		if (stage_text) {
			frm.dashboard.set_headline(stage_text);
		}

		let progress_value = frm.doc.progress || 0;
		if (frm.doc.show_progress_bar !== 0) {
			frm.dashboard.show_progress(__("Task Progress"), progress_value);
		}

		let $bar = frm.dashboard.progress_area
			? frm.dashboard.progress_area.body.find(".progress-bar")
			: null;

		if (frm.doc.status == "Queued" || frm.doc.allow_user_cancellation) {
			frm.add_custom_button(__("Cancel Task"), () => {
				frappe.call({
					method: "frappe.core.doctype.background_task.background_task.stop_task",
					args: { task_id: frm.doc.task_id },
					callback: () => {
						frm.reload_doc();
					},
				});
			});
		}

		frappe.call({
			method: "frappe.core.doctype.background_task.background_task.get_cached_task_status",
			args: { task_id: frm.doc.task_id },
			callback: (r) => {
				if (!r.message) return;
				let cached = r.message;
				if (cached.progress !== undefined && $bar) {
					$bar.css("width", cached.progress + "%");
				}
				if (cached.stage) {
					frm.dashboard.clear_headline();
					frm.dashboard.set_headline(cached.stage);
				}
			},
		});

		frm.task_update_handler = (data) => {
			if (data.task_id !== frm.doc.task_id) return;

			if (data.progress !== undefined && $bar) {
				$bar.css("width", data.progress + "%");
			}

			if (data.stage) {
				frm.dashboard.clear_headline();
				frm.dashboard.set_headline(data.stage);
			}

			if (data.status && data.status !== frm.doc.status) {
				frappe.realtime.off("task_update", frm.task_update_handler);
				frm.task_update_handler = null;
				frm.reload_doc();
			}
		};

		frappe.realtime.on("task_update", frm.task_update_handler);
	},

	on_page_leave(frm) {
		if (frm.task_update_handler) {
			frappe.realtime.off("task_update", frm.task_update_handler);
			frm.task_update_handler = null;
		}
	},
});
