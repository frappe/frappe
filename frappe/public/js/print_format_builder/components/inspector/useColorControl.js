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
	setup_popover_close(control, host);
	return control;
}

// The core popover closes via a bubbled body click, which never arrives in the
// builder (canvas/inspector handlers stop propagation) — close on capture instead
function setup_popover_close(control, host) {
	const hide = () => control.$wrapper.popover("hide");
	const close_if_outside = (e) => {
		if (!document.body.contains(control.$wrapper[0])) {
			document.removeEventListener("click", close_if_outside, true);
			return;
		}
		if (e.target.closest(".color-picker-popover") || host.contains(e.target)) return;
		hide();
	};
	control.$wrapper
		.on("shown.bs.popover", () => document.addEventListener("click", close_if_outside, true))
		.on("hidden.bs.popover", () =>
			document.removeEventListener("click", close_if_outside, true)
		);
	// A swatch is a discrete pick — commit and close
	control.picker?.color_picker_wrapper?.addEventListener("click", (e) => {
		if (e.target.closest(".swatch")) hide();
	});
}
