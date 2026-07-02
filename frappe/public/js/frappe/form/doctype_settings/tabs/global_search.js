// Reuses existing endpoints only:
//  - Global Search Settings doc (read + client.save) for the allowed-list membership
//  - get_global_search_field_options / update_global_search_fields for the field choices
const API = "frappe.desk.doctype.global_search_settings.global_search_settings";
const SETTINGS = "Global Search Settings";

frappe.doctype_settings.register("global-search", function (panel, doctype) {
	load(panel, doctype);
});

function load(panel, doctype) {
	panel.body.empty();
	$(`<div class="text-muted small">${__("Loading")}</div>`).appendTo(panel.body);

	frappe.db
		.get_doc(SETTINGS)
		.then((settings) => {
			const included = (settings.allowed_in_global_search || []).some(
				(r) => r.document_type === doctype
			);
			if (!included) {
				render(panel, doctype, false, []);
				return;
			}
			// Return the inner promise so its failures reach the shared catch.
			return frappe
				.call({ method: `${API}.get_global_search_field_options`, args: { doctype } })
				.then((r) => {
					if (r.exc) throw r.exc;
					render(panel, doctype, true, r.message || []);
				});
		})
		.catch(() => frappe.doctype_settings.render_error(panel, () => load(panel, doctype)));
}

function render(panel, doctype, included, options) {
	const state = { included, fields: options.map((o) => ({ ...o, checked: !!o.checked })) };

	const actions = [
		{
			label: __("Manage priority"),
			click() {
				panel.dialog.hide();
				frappe.set_route("Form", SETTINGS);
			},
		},
	];
	if (included) {
		actions.push({
			label: __("Save"),
			click: () => save(panel, doctype, state),
			variant: "solid",
		});
	}

	panel.set_view({
		title: __("Global Search"),
		description: __(
			"Configure fields to show when searching for {0} globally. Open global search via {1}.",
			[doctype, frappe.ui.keys.get_shortcut_label("Ctrl+G")]
		),
		actions,
		render: (p) => draw(p, doctype, state),
	});
}

function draw(panel, doctype, state) {
	const $body = panel.body.empty();

	$body.append(
		make_switch(
			__("Include {0} in global search", [doctype]),
			state.included,
			(checked, input) => {
				// Membership affects global search for everyone — confirm either way, revert on cancel.
				const message = checked
					? __("Add {0} to global search?", [doctype])
					: __("Remove {0} from global search?", [doctype]);
				frappe.confirm(
					message,
					() => set_included(doctype, checked).then(() => load(panel, doctype)),
					() => (input.checked = !checked)
				);
			}
		)
	);

	if (!state.included) return;

	$(`<div class="text-base pb-3 font-medium">${__("Configure fields")}</div>`).appendTo($body);

	const $input = $('<input type="text" class="form-control input-sm dts-gs-search" />')
		.attr("placeholder", __("Search fields"))
		.appendTo($body);

	const $grid = $('<div class="dts-gs-grid"></div>').appendTo($body);
	state.fields.forEach((o) => {
		const $item = make_check(o.label, o.checked, (v) => (o.checked = v))
			.addClass("dts-gs-item")
			.attr(
				"data-search",
				`${(o.label || "").toLowerCase()} ${(o.value || "").toLowerCase()}`
			);
		$grid.append($item);
	});

	$input.on("input", () => {
		const q = ($input.val() || "").toLowerCase().trim();
		$grid.find(".dts-gs-item").each((i, el) => {
			$(el).toggleClass("hide", !!q && !$(el).attr("data-search").includes(q));
		});
	});
}

// Add/remove the doctype row in Global Search Settings' allowed list (same as that
// settings page does), via a generic doc read + save.
function set_included(doctype, included) {
	return frappe.db.get_doc(SETTINGS).then((settings) => {
		const rows = settings.allowed_in_global_search || [];
		const exists = rows.some((r) => r.document_type === doctype);
		if (included === exists) return;

		settings.allowed_in_global_search = included
			? [...rows, { document_type: doctype }]
			: rows.filter((r) => r.document_type !== doctype);

		return frappe.call({ method: "frappe.client.save", args: { doc: settings } }).then(() => {
			frappe.show_alert({
				message: included
					? __("Added to global search")
					: __("Removed from global search"),
				indicator: "green",
			});
		});
	});
}

function save(panel, doctype, state) {
	const fields = state.fields.filter((o) => o.checked).map((o) => o.value);

	frappe.call({
		method: `${API}.update_global_search_fields`,
		args: { doctype, fields: JSON.stringify(fields) },
		freeze: true,
		freeze_message: __("Updating global search"),
		callback: () => {
			frappe.show_alert({ message: __("Global search updated"), indicator: "green" });
			load(panel, doctype);
		},
	});
}

function make_switch(label, checked, onchange) {
	const $el = $(`<label class="switch-control dts-gs-switch">
			<span class="switch-text"><span class="label-area"></span></span>
			<span class="input-area"><input type="checkbox" role="switch" /></span>
			<span class="switch-visual" aria-hidden="true"><span class="switch-thumb"></span></span>
		</label>`);
	$el.find(".label-area").text(label);
	$el.find("input")
		.prop("checked", checked)
		.on("change", (e) => onchange(e.target.checked, e.target));
	return $el;
}

function make_check(label, checked, onchange) {
	const $label = $(`<label class="dts-check">
			<input type="checkbox" />
			<span class="dts-check-label ellipsis"></span>
		</label>`);
	$label.find(".dts-check-label").text(label);
	$label
		.find("input")
		.prop("checked", checked)
		.on("change", (e) => onchange(e.target.checked));
	return $label;
}
