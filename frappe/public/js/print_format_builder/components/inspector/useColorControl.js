export function mountColorControl(
	host,
	{ value = "", placeholder = "", fieldname = "color", onChange }
) {
	if (!host) return null;
	host.innerHTML = "";
	const control = frappe.ui.form.make_control({
		parent: host,
		df: {
			fieldtype: "Color",
			fieldname,
			placeholder,
			change() {
				onChange(control.get_value() || "");
			},
		},
		render_input: true,
		only_input: true,
	});
	// ControlData re-validates on every `input` event and wipes a partially
	// typed hex code before it's finished. Routing the input event through
	// `change` skips that validate-and-clear so typing a colour isn't erased.
	control.change = control.df.change;
	control.set_value(value || "");
	return control;
}
