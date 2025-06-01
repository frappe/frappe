// Copyright (c) 2022, nts Technologies and contributors
// For license information, please see license.txt

nts.ui.form.on("RQ Job", {
	refresh: function (frm) {
		// Nothing in this form is supposed to be editable.
		frm.disable_form();
		frm.dashboard.set_headline_alert(
			__("This is a virtual doctype and data is cleared periodically.")
		);

		if (["started", "queued"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Force Stop job"), () => {
				nts.confirm(
					__(
						"This will terminate the job immediately and might be dangerous, are you sure? "
					),
					() => {
						nts
							.xcall("nts.core.doctype.rq_job.rq_job.stop_job", {
								job_id: frm.doc.name,
							})
							.then((r) => {
								nts.show_alert(__("Job Stopped Successfully"));
								frm.reload_doc();
							});
					}
				);
			});
		}
	},
});
