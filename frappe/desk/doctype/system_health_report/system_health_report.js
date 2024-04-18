// Copyright (c) 2024, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("System Health Report", {
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
	},
});
