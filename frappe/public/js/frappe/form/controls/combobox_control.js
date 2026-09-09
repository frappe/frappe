// Shared helpers for the combobox-backed Link and Autocomplete controls.

// .input-with-feedback is what dialogs and MultiSelectDialog bind change to
export function mount_combobox(control, combobox) {
	control.combobox = combobox;
	control.$input_area = $(control.input_area);
	combobox.$trigger.prependTo(control.input_area);
	control.$input = $(combobox.input_el).addClass("input-with-feedback");
	control.set_input_attributes();
	control.input = control.$input.get(0);
	control.has_input = true;
	control.bind_change_event();
}

// awesomplete stand-in for desk code and apps; `extra` adds getters
export function awesomplete_shim(control, extra = {}) {
	const combobox = () => control.combobox;
	return Object.defineProperties(
		{
			open: () => combobox() && combobox().open(),
			close: () => combobox() && combobox().close("owner"),
			evaluate: () => {},
			destroy: () => {},
		},
		{
			opened: { get: () => !!(combobox() && combobox().is_open) },
			ul: { get: () => (combobox() && combobox().list_el) || document.createElement("ul") },
			...extra,
		}
	);
}
