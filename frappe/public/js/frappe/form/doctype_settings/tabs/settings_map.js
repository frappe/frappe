// "General" tab — conditional, shown first when this doctype maps related settings.
// Surfaces settings fields from other Single doctypes (Selling Settings, Accounts
// Settings, …) mapped to this doctype via its `DocType Settings Map` record, grouped by their
// source single. Each field is a live control (booleans render as a Switch) that saves
// immediately on change — no Save button. The tab resolves its own data on render (the
// existence check that gated it in index.js was deliberately cheap); saving reuses set_value.
//
// `depends_on` / `read_only_depends_on` on the source fields are honored: each group ships a
// `doc` (the single's read-permitted field values) used to evaluate the expressions, and the
// group re-evaluates reactively whenever one of its fields changes.

frappe.doctype_settings.register("general", function (panel, doctype) {
	panel.set_view({
		title: __("General"),
		description: __("Settings from across the system that apply to {0}.", [doctype]),
		render: (p) => load(p, doctype),
	});
});

function load(panel, doctype) {
	const $body = panel.body.empty();
	frappe.doctype_settings.render_loading($body);

	frappe
		.call({
			method: "frappe.desk.doctype_settings.settings_map.get_settings_map",
			args: { doctype },
		})
		.then((r) => {
			if (r.exc) throw r.exc;
			render(panel, doctype, r.message || []);
		})
		.catch((err) =>
			frappe.doctype_settings.render_error(panel, () => load(panel, doctype), err)
		);
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

	const show_headings = groups.length > 1;
	groups.forEach((group) => {
		group.doc = group.doc || {};
		if (show_headings) $body.append(make_heading(panel, group));
		group.fields.forEach((field) => render_field($body, group, field));
		apply_dependencies(group);
	});
}

// Section heading for one source single: its label plus a jump link to the full
// settings form, for anything beyond the curated subset shown here.
function make_heading(panel, group) {
	const $heading = $('<div class="dts-settings-group-heading"></div>');
	$('<div class="text-base text-ink-gray-5"></div>').text(group.label).appendTo($heading);
	$('<a href="#" class="dts-settings-group-link"></a>')
		.attr("title", __("Open {0}", [group.label]))
		.attr("aria-label", __("Open {0}", [group.label]))
		.append(frappe.utils.icon("arrow-up-right", "sm"))
		.appendTo($heading)
		.on("click", (e) => {
			e.preventDefault();
			panel.dialog.hide();
			frappe.set_route("Form", group.settings);
		});
	group.$heading = $heading;
	return $heading;
}

// One consistent row for every field type: label + description on the left, a compact
// control on the right. Booleans get a bare toggle (the `.switch-control` visual); other
// types get a frappe control rendered input-only so it sits inline instead of stacking.
function render_field($body, group, field) {
	const $row = $('<div class="dts-setting"></div>').appendTo($body);
	field.$row = $row; // referenced by apply_dependencies() to show/hide the field

	const $text = $('<div class="dts-setting-text"></div>').appendTo($row);
	$('<div class="dts-setting-label text-base-medium"></div>').text(field.label).appendTo($text);
	if (field.description) {
		$('<div class="dts-setting-description text-p-sm"></div>')
			.text(field.description)
			.appendTo($text);
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

	const $input = $toggle.find("input").prop("checked", cint(field.value) === 1);
	field.set_locked = (locked) => $input.prop("disabled", locked);

	$input.on("change", (e) => {
		const value = e.target.checked ? 1 : 0;
		on_change(group, field, value, () => (e.target.checked = cint(field.value) === 1));
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
			read_only: field.can_write ? 0 : 1,
			onchange() {
				const value = control.get_value();
				if (value === field.value) return;
				on_change(group, field, value, () => control.set_value(field.value));
			},
		},
	});
	field.set_locked = (locked) => {
		control.df.read_only = locked ? 1 : 0;
		control.refresh();
	};
	control.tooltip && control.tooltip.remove();
	control.set_value(field.value);
	control.refresh();
}

// Apply a change optimistically (so dependents react instantly), then persist; on failure
// roll the doc context back and re-evaluate.
function on_change(group, field, value, revert) {
	group.doc[field.fieldname] = value;
	apply_dependencies(group);
	save(group, field, value, () => {
		group.doc[field.fieldname] = field.value;
		revert && revert();
		apply_dependencies(group);
	});
}

// Persist a single change; revert the control on failure.
function save(group, field, value, revert) {
	if (!field.can_write) return;
	frappe.db
		.set_value(group.settings, group.settings, { [field.fieldname]: value })
		.then(() => {
			field.value = value;
			group.doc[field.fieldname] = value;
			frappe.show_alert({ message: __("{0} updated", [group.label]), indicator: "green" });
		})
		.catch(() => revert && revert());
}

// Show/hide and lock each field in a group per its depends_on / read_only_depends_on,
// evaluated against the group's live `doc`.
function apply_dependencies(group) {
	let any_visible = false;
	group.fields.forEach((field) => {
		const visible = evaluate(field.depends_on, group.doc);
		field.$row.toggle(visible);
		any_visible = any_visible || visible;

		const ro = field.read_only_depends_on && evaluate(field.read_only_depends_on, group.doc);
		field.set_locked && field.set_locked(!field.can_write || !!ro);
	});
	group.$heading && group.$heading.toggle(any_visible);
}

// Mirrors frappe.ui.form.Layout.evaluate_depends_on_value, minus the frm-only `fn:` branch.
// Empty expression → true (visible / no-op for read-only is guarded by the caller).
function evaluate(expression, doc) {
	if (!expression) return true;
	if (typeof expression === "boolean") return expression;
	if (expression.startsWith("eval:")) {
		try {
			return !!frappe.utils.eval(expression.slice(5), { doc, parent: doc });
		} catch (e) {
			// Fail open so one bad expression can't blank the tab.
			// eslint-disable-next-line no-console
			console.warn("settings_map: invalid depends_on", expression, e);
			return true;
		}
	}
	if (expression.startsWith("fn:")) return true; // no frm/script-manager context here
	const value = doc[expression];
	return Array.isArray(value) ? !!value.length : !!value;
}
