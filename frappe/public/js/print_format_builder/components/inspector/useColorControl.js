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
	control.set_value(value || "");
	return control;
}
