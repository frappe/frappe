// "General" tab — conditional, shown first when this doctype maps related settings.
// Surfaces settings fields from other Single doctypes (Selling Settings, Accounts
// Settings, …) linked to this doctype via its `related_settings` table, grouped by their
// source single. Each field is a live control (booleans render as a Switch) that saves
// immediately on change — no Save button. The tab resolves its own data on render (the
// existence check that gated it in index.js was deliberately cheap); saving reuses set_value.

frappe.doctype_settings.register("general", function (panel, doctype) {
	panel.set_view({
		title: __("General"),
		description: __("Settings from across the system that apply to {0}.", [doctype]),
		render: (p) => load(p, doctype),
	});
});

function load(panel, doctype) {
	const $body = panel.body.empty();
	$('<div class="text-muted small"></div>').text(__("Loading")).appendTo($body);

	frappe
		.call({
			method: "frappe.desk.doctype_settings.related_settings.get_related_settings",
			args: { doctype },
		})
		.then((r) => render(panel, doctype, r.message || []));
}

function render(panel, doctype, groups) {
	const $body = panel.body.empty();

	if (!groups.length) {
		frappe.doctype_settings.empty_state($body, {
			icon: "sliders-horizontal",
			title: __("No related settings"),
			description: __("No settings from other areas are linked to {0}.", [doctype]),
		});
		return;
	}

	// Flat list — every field across every source single, no per-single section headers.
	// Each field keeps its `group` context (settings doctype + can_write) for saving.
	groups.forEach((group) => group.fields.forEach((field) => render_field($body, group, field)));
}

// One consistent row for every field type: label + description on the left, a compact
// control on the right. Booleans get a bare toggle (the `.switch-control` visual); other
// types get a frappe control rendered input-only so it sits inline instead of stacking.
function render_field($body, group, field) {
	const $row = $('<div class="dts-setting"></div>').appendTo($body);

	const $text = $('<div class="dts-setting-text"></div>').appendTo($row);
	$('<div class="dts-setting-label"></div>').text(field.label).appendTo($text);
	if (field.description) {
		$('<div class="dts-setting-description"></div>').text(field.description).appendTo($text);
	}

	const $control = $('<div class="dts-setting-control"></div>').appendTo($row);
	if (field.fieldtype === "Check") {
		render_toggle($control, group, field);
	} else {
		render_input($control, group, field);
	}
}

function render_toggle($control, group, field) {
	const $toggle = $(`<label class="switch-control dts-setting-toggle">
			<span class="input-area"><input type="checkbox" role="switch" /></span>
			<span class="switch-visual" aria-hidden="true"><span class="switch-thumb"></span></span>
		</label>`).appendTo($control);

	const $input = $toggle
		.find("input")
		.prop("checked", cint(field.value) === 1)
		.prop("disabled", !group.can_write);

	$input.on("change", (e) => {
		const value = e.target.checked ? 1 : 0;
		save(group, field, value, () => (e.target.checked = cint(field.value) === 1));
	});
}

function render_input($control, group, field) {
	const control = frappe.ui.form.make_control({
		parent: $control.get(0),
		render_input: true,
		only_input: true,
		df: {
			fieldname: field.fieldname,
			fieldtype: field.fieldtype,
			options: field.options,
			read_only: group.can_write ? 0 : 1,
			onchange() {
				const value = control.get_value();
				if (value === field.value) return;
				save(group, field, value, () => control.set_value(field.value));
			},
		},
	});
	control.set_value(field.value);
	control.refresh();
}

// Persist a single change; revert the control on failure.
function save(group, field, value, revert) {
	if (!group.can_write) return;
	frappe.db
		.set_value(group.settings, group.settings, { [field.fieldname]: value })
		.then(() => {
			field.value = value;
			frappe.show_alert({ message: __("{0} updated", [group.label]), indicator: "green" });
		})
		.catch(() => revert && revert());
}
