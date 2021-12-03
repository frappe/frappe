frappe.provide("frappe.model");

/*
	Common class for handling client side interactions that
	apply to both DocType form and customize form.
*/
frappe.model.DocTypeController = class DocTypeController extends frappe.ui.form.Controller {

	max_attachments() {
		if (!this.frm.doc.max_attachments) {
			return;
		}
		const is_attach_field = (f) => ["Attach", "Attach Image"].includes(f.fieldtype);
		const no_of_attach_fields = this.frm.doc.fields.filter(is_attach_field).length;

		if (no_of_attach_fields > this.frm.doc.max_attachments) {
			this.frm.set_value("max_attachments", no_of_attach_fields);
			const label = this.frm.get_docfield("max_attachments").label;
			frappe.show_alert(
				__("Number of attachment fields are more than {}, limit updated to {}.", [label, no_of_attach_fields]));
		}
	}
}
