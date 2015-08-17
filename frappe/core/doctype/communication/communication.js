frappe.ui.form.on("Communication", "setup", function(frm) {
	frappe.call({
		method:"frappe.core.doctype.doctype.communication.get_convert_to",
		callback: function(r) {
			frappe.communication_convert_to = r.message;
			frm.convert_to_click = [];
			$.each(r.message, function(i, v) {
				frm.convert_to_click.append({label:__(v), value:v, action:function() {
					frm.convert_to($(this).attr("data-value"));
				}});
			});
			frm.set_convert_button();
		}
	});

	frm.set_convert_button = function() {
		frm.add_custom_button(__("Add To"), frm.convert_to_click);
	};

	frm.convert_to = function(doctype) {

	};
});

frappe.ui.form.on("Communication", "refresh", function(frm) {
	frm.convert_to_click && frm.set_convert_button();
	frm.subject_field = "subject";

	if(frm.doc.reference_doctype && frm.doc.reference_name) {
		frm.add_custom_button(__(frm.doc.reference_name), function() {
			frappe.set_route("Form", frm.doc.reference_doctype, frm.doc.reference_name);
		}, frappe.boot.doctype_icons[frm.doc.reference_doctype]);
	} else {
		// if an unlinked communication, set email field
		if (frm.doc.sent_or_received==="Received") {
			frm.email_field = "sender";
		} else {
			frm.email_field = "recipients";
		}
	}

	if(frm.doc.status==="Open") {
		frm.add_custom_button("Close", function() {
			frm.set_value("status", "Closed");
			frm.save();
		});
	} else if (frm.doc.status !== "Linked") {
		frm.add_custom_button("Reopen", function() {
			frm.set_value("status", "Open");
			frm.save();
		});
	}
});

frappe.ui.form.on("Communication", "onload", function(frm) {
	if(frm.doc.content) {
		frm.doc.content = frappe.utils.remove_script_and_style(frm.doc.content);
	}
	frm.set_query("reference_doctype", function() {
		return {
			filters: {
				"issingle": 0,
				"istable": 0
			}
		}
	})
});
