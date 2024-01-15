// Copyright (c) 2024, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Drawing", {
	refresh(frm) {
		frm.get_field("svg_preview").$wrapper.html(frm.doc.svg);
	},
	onload(frm) {
		// Excalidraw package needs this to be present
		frappe.provide("process.env");
		frappe.require(["whiteboard_editor.bundle.jsx"]).then(() => {
			frappe.whiteboard = new frappe.ui.WhiteboardEditor({
				wrapper: frm.get_field("drawing_editor").$wrapper,
			});
		});
	},
});
