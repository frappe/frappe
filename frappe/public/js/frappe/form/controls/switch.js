// A sliding toggle. Reuses ControlCheck wholesale — same checkbox input and
// 0/1 value semantics (get_values() returns 1/0, validate, set_input, read-only
// disp) — and only swaps the markup so CSS can skin it as a switch. Usable
// anywhere a control is built (FieldGroup, Dialog, forms) via fieldtype "Switch".
frappe.ui.form.ControlSwitch = class ControlSwitch extends frappe.ui.form.ControlCheck {
	make_input() {
		super.make_input();
		// Communicate toggle-switch semantics to assistive technology (otherwise
		// the underlying checkbox is announced as a checkbox, not a switch).
		this.$input.attr("role", "switch");
	}

	make_wrapper() {
		// Everything is inside the <label>, so clicking the text toggles the switch.
		// The real checkbox lives in `.input-area` (visually hidden via CSS); the
		// `.switch-visual` sibling reflects its :checked state with `:has()`.
		// set_label() fills `.label-area`; set_description() fills `.help-box`.
		this.$wrapper = $(`<div class="form-group frappe-control">
			<label class="switch-control">
				<span class="switch-text">
					<span class="label-area"></span>
					<span class="disp-area"></span>
					<div class="help-box small text-extra-muted hide"></div>
				</span>
				<span class="input-area"></span>
				<span class="switch-visual" aria-hidden="true">
					<span class="switch-thumb"></span>
				</span>
				<span class="ml-1 help"></span>
			</label>
		</div>`).appendTo(this.parent);
	}
};
