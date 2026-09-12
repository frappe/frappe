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
			// the grid closes the classic dropdown on scroll; this panel follows
			// its trigger, so a scroll only needs a reposition
			close: () => combobox() && combobox().reposition(),
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
