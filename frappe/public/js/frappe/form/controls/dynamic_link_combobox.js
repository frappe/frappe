// Dynamic Link on top of ControlLinkCombobox.
// Picked by make_control for Dynamic Link fields under the same setting.

frappe.ui.form.ControlDynamicLinkCombobox = class ControlDynamicLinkCombobox extends (
	frappe.ui.form.ControlLinkCombobox
) {
	get_options() {
		return frappe.ui.form.ControlDynamicLink.prototype.get_options.call(this);
	}
};
