// Copyright (c) 2024, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("System Health Report", {
	onload(frm) {
		let poll_attempts = 0;
		const interval = setInterval(() => {
			frappe
				.xcall(
					"frappe.desk.doctype.system_health_report.system_health_report.get_job_status",
					{ job_id: frm.doc.test_job_id }
				)
				.then((status) => {
					poll_attempts += 1;
					if (["finished", "failed"].includes(status) || poll_attempts > 30) {
						clearInterval(interval);
					}
					status && frm.set_value("background_jobs_check", status);
				});
		}, 1000);
	},
	refresh(frm) {
		frm.set_value("socketio_ping_check", "Fail");
		frappe.realtime.on("pong", () => {
			frm.set_value("socketio_ping_check", "Pass");
			frm.set_value(
				"socketio_transport_mode",
				frappe.realtime.socket.io?.engine?.transport?.name
			);
		});
		frappe.realtime.emit("ping");
		frm.disable_save();
	},
});
