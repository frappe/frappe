// Copyright (c) 2026, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("MapReduce Job", {
	refresh(frm) {
		frm.add_custom_button(
			__("Force Retry"),
			() => {
				frappe.confirm(
					__(
						"This will force reset status of running tasks to 'queued' and will reschedule. Are you sure?"
					),
					() => {
						frm.call({
							method: "frappe.core.doctype.mapreduce_job.mapreduce_job.force_retry",
							args: {
								job: frm.doc.name,
							},
						}).then((r) => {
							if (!r.exc) {
								frappe.show_alert(__("Running tasks requeued for processing"));
								frm.reload_doc();
							}
						});
					}
				);
			},
			__("Actions")
		);

		frm.call({
			method: "frappe.core.doctype.mapreduce_job.mapreduce_job.get_progress",
			args: {
				job: frm.doc.name,
			},
		}).then((r) => {
			if (!r.exc) {
				frm.dashboard.add_progress("Task completion", r.message.progress, "");
				if (r.message.status == "Queued") {
					add_control_button(
						frm,
						"frappe.core.doctype.mapreduce_job.mapreduce_job.pause_execution",
						"Pause",
						frm.doc.name,
						"Tasks paused"
					);
				} else if (r.message.status == "Paused") {
					add_control_button(
						frm,
						"frappe.core.doctype.mapreduce_job.mapreduce_job.start_execution",
						"Resume",
						frm.doc.name,
						"Tasks queued"
					);
				}
			}
		});
	},
});
function add_control_button(frm, method, title, job_id, msg) {
	frm.add_custom_button(__(title), () => {
		frm.call({
			method: method,
			args: {
				job: job_id,
			},
		}).then((r) => {
			if (!r.exc) {
				frappe.show_alert(__(msg));
				frm.reload_doc();
			}
		});
	});
}
