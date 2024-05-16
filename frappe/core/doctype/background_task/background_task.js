// Copyright (c) 2024, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Background Task", {
	refresh(frm) {
		if (["Queued", "In Progress"].includes(frm.doc.status)) {
			frm.add_custom_button("Stop Task", () => {
				frappe.call({
					method: "frappe.core.doctype.background_task.background_task.stop_task",
					args: {
						task_id: frm.doc.task_id,
					},
					callback: (r) => {
						frappe.toast(r.message);
						frm.reload_doc();
					},
				});
			});
		}
	},
	setup(frm) {
		frappe.realtime.on("background_task", (data) => {
			if (data.background_task_id === frm.doc.task_id) {
				frm.dashboard.show_progress(__("Task Progress"), data.progress, data.message);
			}
		});
	},
});
