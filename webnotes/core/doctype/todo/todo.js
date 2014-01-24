// bind events

wn.ui.form.on("ToDo", "refresh", function(frm) {
	frm.add_custom_button((frm.doc.status=="Open" ? wn._("Close") : wn._("Re-open")), function() {
		frm.set_value("status", frm.doc.status=="Open" ? "Closed" : "Open");
		frm.save();
	})
})