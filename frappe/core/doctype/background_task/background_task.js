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
		} else {
			frm.add_custom_button("Retry Task", () => {
				const dialog = new frappe.ui.Dialog({
					title: __("Retry Task"),
					fields: [
						{
							fieldname: "method",
							label: __("Method"),
							fieldtype: "Data",
							default: frm.doc.method,
						},
						{
							fieldname: "queue",
							label: __("Queue"),
							fieldtype: "Data",
							default: frm.doc.queue,
						},
						{
							fieldname: "timeout",
							label: __("Timeout"),
							fieldtype: "Int",
							default: frm.doc.timeout,
						},
						{
							fieldname: "success_callback",
							label: __("Success Callback"),
							fieldtype: "Data",
							default: frm.doc.success_callback,
						},
						{
							fieldname: "failure_callback",
							label: __("Failure Callback"),
							fieldtype: "Data",
							default: frm.doc.failure_callback,
						},
						{
							fieldname: "stopped_callback",
							label: __("Stopped Callback"),
							fieldtype: "Data",
							default: frm.doc.stopped_callback,
						},
						{
							fieldname: "at_front",
							label: __("Add to the front of the queue?"),
							fieldtype: "Check",
							default: frm.doc.at_front,
						},
						{
							fieldname: "kwargs",
							label: __(
								"JSON containing miscellaneous keyword arguments for the method"
							),
							fieldtype: "Code",
							default: frm.doc.kwargs,
						},
					],
					primary_action_label: "Retry",
					primary_action: (data) => {
						frappe.call({
							method: "frappe.core.doctype.background_task.background_task.enqueue_task",
							args: {
								method: data.method,
								queue: data.queue,
								timeout: data.timeout,
								success_callback: data.success_callback,
								failure_callback: data.failure_callback,
								stopped_callback: data.stopped_callback,
								at_front: data.at_front,
								original_task: frm.doc.name,
								kwargs: data.kwargs,
							},
							callback: (r) => {
								if (!r.exc) {
									dialog.hide();
									frappe.toast("Re-queued task");
								}
							},
						});
					},
				});
				dialog.show();
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
