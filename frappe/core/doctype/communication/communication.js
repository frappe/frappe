frappe.ui.form.on("setup", "Communication", function(frm) {
	frappe.call({
		method:"frappe.core.doctype.doctype.communication.get_convert_to",
		callback: function(r) {
			frappe.communication_convert_to = r.message;
			frm.convert_to_click = [];
			$.each(r.message, function(i, v) {
				frm.convert_to_click.append({label:__(v), value:v, function() {
					frm.convert_to($(this).attr("data-value"));
				}})
			})
			frm.set_convert_button();
		}
	});

	frm.set_convert_button = function() {
		frm.add_custom_button(__("Add To"), frm.convert_to_click);
	}

	frm.convert_to = function(doctype) {

	}
});

frappe.ui.form.on("refresh", "Communication", function(frm) {
	frm.convert_to_click && frm.set_convert_button();
});

frappe.ui.form.on("onload", "Communication", function(frm) {
	if(doc.content) {
		doc.content = frappe.utils.remove_script_and_style(doc.content);
	}
});
